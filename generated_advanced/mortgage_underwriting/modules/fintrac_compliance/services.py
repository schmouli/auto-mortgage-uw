```python
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Tuple
import asyncio

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.fintrac_compliance import FintracVerification, FintracReport, RiskLevel, VerificationMethod, ReportType
from app.schemas.fintrac_compliance import (
    IdentityVerificationCreateRequest,
    TransactionReportCreateRequest,
    RiskAssessmentResponse,
    VerificationStatusResponse,
    TransactionReportResponse,
    IdentityVerificationResponse
)
from app.core.security import encrypt_data
from app.exceptions.fintrac_exceptions import (
    FintracComplianceError,
    VerificationNotFoundError,
    InvalidAmountError
)


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
        # Encrypt sensitive data before storing
        encrypted_id_number = encrypt_data(request.id_number_encrypted)
        
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
            verified_at=datetime.utcnow(),
            is_pep=request.is_pep,
            is_hio=request.is_hio,
            risk_level=risk_level,
            record_created_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            changed_by=changed_by_user_id
        )
        
        self.db.add(verification)
        await self.db.commit()
        await self.db.refresh(verification)
        
        return IdentityVerificationResponse.model_validate(verification)

    async def get_verification_status(self, application_id: int) -> VerificationStatusResponse:
        """
        Get the verification status for an application
        """
        result = await self.db.execute(
            select(FintracVerification)
            .where(FintracVerification.application_id == application_id)
            .order_by(FintracVerification.created_at.desc())
            .limit(1)
        )
        verification = result.scalar_one_or_none()
        
        if not verification:
            return VerificationStatusResponse(
                has_verification=False,
                latest_verification=None,
                requires_enhanced_due_diligence=False
            )
            
        requires_edd = (
            verification.risk_level == RiskLevel.HIGH or 
            verification.is_pep or 
            verification.is_hio
        )
        
        return VerificationStatusResponse(
            has_verification=True,
            latest_verification=IdentityVerificationResponse.model_validate(verification),
            requires_enhanced_due_diligence=requires_edd
        )

    async def file_transaction_report(
        self,
        application_id: int,
        request: TransactionReportCreateRequest,
        changed_by_user_id: int
    ) -> TransactionReportResponse:
        """
        File a FINTRAC transaction report, checking for structuring patterns
        """
        # Validate amount
        if request.amount <= 0:
            raise InvalidAmountError("Transaction amount must be positive")
            
        # Check for structuring if it's a cash transaction under $10k
        is_structuring_suspected = False
        if (
            request.report_type == ReportType.LARGE_CASH_TRANSACTION and
            request.amount < Decimal('10000') and
            request.currency == "CAD"
        ):
            is_structuring_suspected = await self._check_for_structuring(application_id, request.amount, request.report_date)
        
        # If structuring suspected, change report type
        report_type = request.report_type
        if is_structuring_suspected:
            report_type = ReportType.SUSPICIOUS_TRANSACTION
            
        report = FintracReport(
            application_id=application_id,
            report_type=report_type,
            amount=request.amount,
            currency=request.currency,
            report_date=request.report_date,
            created_by=request.created_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            changed_by=changed_by_user_id
        )
        
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        
        return TransactionReportResponse.model_validate(report)

    async def _check_for_structuring(
        self,
        application_id: int,
        current_amount: Decimal,
        current_date: datetime
    ) -> bool:
        """
        Check for potential structuring by looking at recent transactions
        """
        # Look for other cash transactions in the same 24-hour period
        start_time = current_date - timedelta(hours=24)
        end_time = current_date + timedelta(hours=24)
        
        result = await self.db.execute(
            select(func.sum(FintracReport.amount))
            .where(and_(
                FintracReport.application_id == application_id,
                FintracReport.report_type == ReportType.LARGE_CASH_TRANSACTION,
                FintracReport.currency == "CAD",
                FintracReport.report_date >= start_time,
                FintracReport.report_date <= end_time,
                FintracReport.deleted_at.is_(None)
            ))
        )
        
        total_amount = result.scalar() or Decimal('0')
        combined_amount = total_amount + current_amount
        
        return combined_amount > Decimal('10000')

    async def list_transaction_reports(self, application_id: int) -> List[TransactionReportResponse]:
        """
        List all transaction reports for an application
        """
        result = await self.db.execute(
            select(FintracReport)
            .where(and_(
                FintracReport.application_id == application_id,
                FintracReport.deleted_at.is_(None)
            ))
            .order_by(FintracReport.report_date.desc())
        )
        
        reports = result.scalars().all()
        return [TransactionReportResponse.model_validate(r) for r in reports]

    async def get_client_risk_assessment(self, client_id: int) -> RiskAssessmentResponse:
        """
        Get the current risk assessment for a client
        """
        result = await self.db.execute(
            select(FintracVerification)
            .where(FintracVerification.client_id == client_id)
            .order_by(FintracVerification.created_at.desc())
            .limit(1)
        )
        verification = result.scalar_one_or_none()
        
        if not verification:
            raise VerificationNotFoundError(f"No verification found for client {client_id}")
            
        requires_edd = (
            verification.risk_level == RiskLevel.HIGH or 
            verification.is_pep or 
            verification.is_hio
        )
        
        return RiskAssessmentResponse(
            client_id=client_id,
            requires_enhanced_due_diligence=requires_edd,
            risk_level=verification.risk_level,
            is_pep=verification.is_pep,
            is_hio=verification.is_hio,
            last_verification_date=verification.verified_at
        )

    async def soft_delete_report(self, report_id: int, changed_by_user_id: int) -> None:
        """
        Soft delete a FINTRAC report (never hard delete)
        """
        result = await self.db.execute(
            select(FintracReport).where(FintracReport.id == report_id)
        )
        report = result.scalar_one_or_none()
        
        if not report:
            raise FintracComplianceError("Report not found")
            
        report.deleted_at = datetime.utcnow()
        report.changed_by = changed_by_user_id
        report.updated_at = datetime.utcnow()
        
        await self.db.commit()
```