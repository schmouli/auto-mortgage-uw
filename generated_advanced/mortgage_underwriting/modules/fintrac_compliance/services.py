from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.common.security import encrypt_pii
from mortgage_underwriting.modules.fintrac.models import FintracVerification, FintracReport
from mortgage_underwriting.modules.fintrac.schemas import (
    IdentityVerificationCreate,
    IdentityVerificationUpdate,
    TransactionReportCreate,
    TransactionReportUpdate,
)
from mortgage_underwriting.modules.application.models import MortgageApplication
from mortgage_underwriting.modules.client.models import Client

logger = structlog.get_logger()


class FintracComplianceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def verify_identity(
        self, 
        application_id: int, 
        payload: IdentityVerificationCreate,
        verified_by_user_id: int
    ) -> FintracVerification:
        """Submit identity verification for a client in an application.
        
        Args:
            application_id: ID of the mortgage application
            payload: Identity verification data
            verified_by_user_id: User ID performing verification
            
        Returns:
            Created FintracVerification record
            
        Raises:
            NotFoundError: If application or client not found
            AppException: If verification already exists
        """
        logger.info(
            "fintrac_verify_identity",
            application_id=application_id,
            client_id=payload.client_id
        )

        # Validate application exists
        app_result = await self.db.execute(
            select(MortgageApplication).where(MortgageApplication.id == application_id)
        )
        application = app_result.scalar_one_or_none()
        if not application:
            raise NotFoundError(detail="Application not found", error_code="FINTRAC_001")

        # Validate client belongs to application
        client_result = await self.db.execute(
            select(Client).where(and_(Client.id == payload.client_id, Client.id == application.client_id))
        )
        client = client_result.scalar_one_or_none()
        if not client:
            raise NotFoundError(detail="Client not found or not part of application", error_code="FINTRAC_002")

        # Check if verification already exists
        existing_result = await self.db.execute(
            select(FintracVerification).where(
                and_(
                    FintracVerification.application_id == application_id,
                    FintracVerification.client_id == payload.client_id
                )
            )
        )
        if existing_result.scalar_one_or_none():
            raise AppException(
                detail="Verification already exists for client", 
                error_code="FINTRAC_006"
            )

        # Determine risk level
        risk_level = "low"
        if payload.is_pep or payload.is_hio:
            risk_level = "high"
        elif payload.verification_method == "credit_file":
            risk_level = "medium"

        # Encrypt ID number
        encrypted_id = encrypt_pii(payload.id_number)

        # Calculate 5-year retention deadline
        retention_deadline = datetime.utcnow() + timedelta(days=5*365)

        # Create verification record
        verification = FintracVerification(
            application_id=application_id,
            client_id=payload.client_id,
            verification_method=payload.verification_method,
            id_type=payload.id_type,
            id_number_encrypted=encrypted_id,
            id_expiry_date=payload.id_expiry_date,
            id_issuing_province=payload.id_issuing_province,
            verified_by=verified_by_user_id,
            verified_at=datetime.utcnow(),
            is_pep=payload.is_pep,
            is_hio=payload.is_hio,
            risk_level=risk_level,
            record_created_at=datetime.utcnow(),
            retention_deadline=retention_deadline
        )

        self.db.add(verification)
        await self.db.commit()
        await self.db.refresh(verification)

        return verification

    async def get_verification_status(self, application_id: int) -> Optional[FintracVerification]:
        """Get verification status for an application.
        
        Args:
            application_id: ID of the mortgage application
            
        Returns:
            FintracVerification record or None
        """
        logger.info("fintrac_get_verification", application_id=application_id)
        
        result = await self.db.execute(
            select(FintracVerification)
            .options(selectinload(FintracVerification.client))
            .where(FintracVerification.application_id == application_id)
        )
        return result.scalar_one_or_none()

    async def file_transaction_report(
        self, 
        application_id: int, 
        payload: TransactionReportCreate,
        created_by_user_id: int
    ) -> FintracReport:
        """File a FINTRAC transaction report.
        
        Args:
            application_id: ID of the mortgage application
            payload: Transaction report data
            created_by_user_id: User ID creating the report
            
        Returns:
            Created FintracReport record
        """
        logger.info(
            "fintrac_file_transaction_report",
            application_id=application_id,
            report_type=payload.report_type,
            amount=float(payload.amount)
        )

        # Validate application exists
        app_result = await self.db.execute(
            select(MortgageApplication).where(MortgageApplication.id == application_id)
        )
        application = app_result.scalar_one_or_none()
        if not application:
            raise NotFoundError(detail="Application not found", error_code="FINTRAC_001")

        # Check for structuring (multiple cash transactions < $10,000 within 24 hours)
        structuring_detected = False
        if payload.report_type == "large_cash_transaction" and payload.amount < Decimal('10000'):
            twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
            structuring_query = select(FintracReport).where(
                and_(
                    FintracReport.application_id == application_id,
                    FintracReport.report_type == "large_cash_transaction",
                    FintracReport.created_at >= twenty_four_hours_ago,
                    FintracReport.amount < Decimal('10000')
                )
            )
            structuring_result = await self.db.execute(structuring_query)
            if structuring_result.scalars().all():
                structuring_detected = True
                logger.warning(
                    "fintrac_structuring_detected",
                    application_id=application_id,
                    amount=float(payload.amount)
                )

        # Determine if high-value flag is required
        requires_high_value_flag = payload.amount > Decimal('10000')
        
        # Log high-value transaction requirement
        if requires_high_value_flag:
            logger.info(
                "fintrac_high_value_transaction",
                application_id=application_id,
                amount=float(payload.amount),
                requires_explicit_flag=True
            )

        # Calculate 5-year retention deadline
        retention_deadline = datetime.utcnow() + timedelta(days=5*365)

        # Create report record
        report = FintracReport(
            application_id=application_id,
            report_type=payload.report_type,
            amount=payload.amount,
            currency=payload.currency,
            report_date=payload.report_date,
            created_by=created_by_user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            retention_deadline=retention_deadline,
            requires_high_value_flag=requires_high_value_flag
        )

        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)

        return report

    async def list_transaction_reports(self, application_id: int) -> List[FintracReport]:
        """List all FINTRAC reports for an application.
        
        Args:
            application_id: ID of the mortgage application
            
        Returns:
            List of FintracReport records
        """
        logger.info("fintrac_list_transaction_reports", application_id=application_id)
        
        result = await self.db.execute(
            select(FintracReport)
            .where(FintracReport.application_id == application_id)
            .order_by(FintracReport.created_at.desc())
        )
        return result.scalars().all()

    async def get_risk_assessment(self, client_id: int) -> RiskAssessmentResponse:
        """Get risk assessment for a client based on their latest verification.
        
        Args:
            client_id: ID of the client
            
        Returns:
            RiskAssessmentResponse object
        """
        logger.info("fintrac_get_risk_assessment", client_id=client_id)
        
        # Get latest verification for client
        result = await self.db.execute(
            select(FintracVerification)
            .where(FintracVerification.client_id == client_id)
            .order_by(FintracVerification.record_created_at.desc())
            .limit(1)
        )
        verification = result.scalar_one_or_none()
        
        # Default risk profile if no verification exists
        if not verification:
            return RiskAssessmentResponse(
                client_id=client_id,
                risk_level="unknown",
                risk_score=0,
                requires_enhanced_due_diligence=False,
                last_verification_date=None
            )
        
        # Map risk level to score
        risk_scores = {"low": 1, "medium": 2, "high": 3}
        
        return RiskAssessmentResponse(
            client_id=client_id,
            risk_level=verification.risk_level,
            risk_score=risk_scores.get(verification.risk_level, 0),
            requires_enhanced_due_diligence=verification.risk_level in ["medium", "high"],
            last_verification_date=verification.record_created_at
        )