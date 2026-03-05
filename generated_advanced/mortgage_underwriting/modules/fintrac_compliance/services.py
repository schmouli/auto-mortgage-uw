import structlog
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Tuple
import asyncio

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.fintrac.models import FintracVerification, FintracReport, FintracAuditLog, RiskLevel, VerificationMethod, ReportType
from mortgage_underwriting.modules.fintrac.schemas import (
    IdentityVerificationCreateRequest,
    TransactionReportCreateRequest,
    RiskAssessmentResponse,
    VerificationStatusResponse,
    TransactionReportResponse,
    IdentityVerificationResponse
)
from mortgage_underwriting.common.security import encrypt_pii
from mortgage_underwriting.modules.fintrac.exceptions import (
    FintracComplianceError,
    VerificationNotFoundError,
    InvalidAmountError,
    ReportSubmissionError
)

logger = structlog.get_logger()


class FintracService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_identity_verification(
        self,
        application_id: int,
        client_id: int,
        request: IdentityVerificationCreateRequest,
        changed_by_user_id: int
    ) -> IdentityVerificationResponse:
        """
        Create a new identity verification record with appropriate risk assessment
        """
        try:
            # Encrypt sensitive data before storing
            encrypted_id_number = encrypt_pii(request.id_number_encrypted)
            
            # Determine risk level based on compliance rules
            risk_level = RiskLevel.LOW
            if request.is_pep or request.is_hio:
                risk_level = RiskLevel.HIGH
            
            verification = FintracVerification(
                application_id=application_id,
                client_id=client_id,
                verification_method=request.verification_method,
                id_type=request.id_type,
                id_number_encrypted=encrypted_id_number,
                id_expiry_date=request.id_expiry_date,
                id_issuing_province=request.id_issuing_province,
                verified_by=request.verified_by,
                is_pep=request.is_pep,
                is_hio=request.is_hio,
                risk_level=risk_level
            )
            
            self.db.add(verification)
            await self.db.commit()
            await self.db.refresh(verification)
            
            logger.info(
                "identity_verification_created",
                verification_id=verification.id,
                application_id=application_id,
                client_id=client_id,
                risk_level=risk_level.value
            )
            
            return IdentityVerificationResponse.model_validate(verification)
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error("database_error", error=str(e))
            raise FintracComplianceError("Failed to create identity verification") from e
        except Exception as e:
            await self.db.rollback()
            logger.error("unexpected_error", error=str(e))
            raise FintracComplianceError("Unexpected error during verification creation") from e

    async def get_verification_status(self, application_id: int) -> VerificationStatusResponse:
        """
        Get the latest verification status for an application
        """
        try:
            stmt = select(FintracVerification).where(
                FintracVerification.application_id == application_id
            ).order_by(FintracVerification.verified_at.desc()).limit(1)
            
            result = await self.db.execute(stmt)
            verification = result.scalar_one_or_none()
            
            if not verification:
                raise VerificationNotFoundError(f"No verification found for application {application_id}")
            
            logger.info(
                "verification_status_retrieved",
                application_id=application_id,
                verification_id=verification.id
            )
            
            return VerificationStatusResponse(
                verification_id=verification.id,
                application_id=application_id,
                verification_method=verification.verification_method,
                verified_at=verification.verified_at,
                risk_level=verification.risk_level,
                is_pep=verification.is_pep,
                is_hio=verification.is_hio
            )
        except VerificationNotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.error("database_error", error=str(e))
            raise FintracComplianceError("Failed to retrieve verification status") from e
        except Exception as e:
            logger.error("unexpected_error", error=str(e))
            raise FintracComplianceError("Unexpected error retrieving verification status") from e

    async def file_transaction_report(
        self,
        client_id: int,
        request: TransactionReportCreateRequest
    ) -> TransactionReportResponse:
        """
        File a new transaction report with FINTRAC requirements
        """
        try:
            # Validate amount for large transaction reporting
            if request.amount > Decimal("10000") and request.report_type == ReportType.LARGE_CASH_TRANSACTION:
                logger.warning(
                    "large_transaction_detected",
                    client_id=client_id,
                    amount=float(request.amount),
                    currency=request.currency
                )
            
            report = FintracReport(
                client_id=client_id,
                report_type=request.report_type,
                amount=request.amount,
                currency=request.currency,
                report_date=request.report_date,
                created_by=request.created_by,
                application_id=getattr(request, 'application_id', None)
            )
            
            self.db.add(report)
            await self.db.flush()
            
            # Create audit log entry
            audit_log = FintracAuditLog(
                report_id=report.id,
                action="created",
                changed_by=request.created_by,
                details=f"Report filed for {request.report_type.value}"
            )
            
            self.db.add(audit_log)
            await self.db.commit()
            await self.db.refresh(report)
            
            logger.info(
                "transaction_report_filed",
                report_id=report.id,
                client_id=client_id,
                report_type=request.report_type.value,
                amount=float(request.amount)
            )
            
            return TransactionReportResponse.model_validate(report)
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error("database_error", error=str(e))
            raise ReportSubmissionError("Failed to file transaction report") from e
        except Exception as e:
            await self.db.rollback()
            logger.error("unexpected_error", error=str(e))
            raise ReportSubmissionError("Unexpected error filing transaction report") from e

    async def list_transaction_reports(
        self, 
        client_id: int, 
        skip: int = 0, 
        limit: int = 50
    ) -> Tuple[List[TransactionReportResponse], int]:
        """
        List transaction reports for a client with pagination
        """
        try:
            # FIXED: Enforce maximum limit of 100 records per page
            limit = min(limit, 100)
            
            # FIXED: Use selectinload to prevent N+1 query issue
            stmt = select(FintracReport).where(
                FintracReport.client_id == client_id
            ).options(
                selectinload(FintracReport.audit_logs)
            ).offset(skip).limit(limit)
            
            result = await self.db.execute(stmt)
            reports = result.scalars().all()
            
            # Get total count
            count_stmt = select(func.count()).select_from(FintracReport).where(
                FintracReport.client_id == client_id
            )
            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar_one()
            
            logger.info(
                "transaction_reports_listed",
                client_id=client_id,
                count=len(reports),
                skip=skip,
                limit=limit
            )
            
            report_responses = [
                TransactionReportResponse.model_validate(report) 
                for report in reports
            ]
            
            return report_responses, total
        except SQLAlchemyError as e:
            logger.error("database_error", error=str(e))
            raise FintracComplianceError("Failed to list transaction reports") from e
        except Exception as e:
            logger.error("unexpected_error", error=str(e))
            raise FintracComplianceError("Unexpected error listing transaction reports") from e

    async def get_client_risk_assessment(self, client_id: int) -> RiskAssessmentResponse:
        """
        Generate a risk assessment for a client based on their verification history
        """
        try:
            # Get latest verification for client
            stmt = select(FintracVerification).where(
                FintracVerification.client_id == client_id
            ).order_by(FintracVerification.verified_at.desc()).limit(1)
            
            result = await self.db.execute(stmt)
            verification = result.scalar_one_or_none()
            
            if not verification:
                # Default to low risk if no verification found
                risk_level = RiskLevel.LOW
                factors = ["No prior verifications"]
            else:
                risk_level = verification.risk_level
                factors = []
                if verification.is_pep:
                    factors.append("Politically Exposed Person")
                if verification.is_hio:
                    factors.append("High Impact Organization")
                if not factors:
                    factors.append("Standard verification")
            
            logger.info(
                "risk_assessment_generated",
                client_id=client_id,
                risk_level=risk_level.value,
                factors=factors
            )
            
            return RiskAssessmentResponse(
                client_id=client_id,
                risk_level=risk_level,
                last_assessed_at=datetime.utcnow(),
                factors=factors
            )
        except SQLAlchemyError as e:
            logger.error("database_error", error=str(e))
            raise FintracComplianceError("Failed to generate risk assessment") from e
        except Exception as e:
            logger.error("unexpected_error", error=str(e))
            raise FintracComplianceError("Unexpected error generating risk assessment") from e
```

```