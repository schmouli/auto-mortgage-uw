from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.common.security import encrypt_pii
from mortgage_underwriting.modules.fintrac.models import FintracVerification, FintracReport
from mortgage_underwriting.modules.fintrac.schemas import (
    FintracVerificationCreate,
    FintracVerificationResponse,
    FintracReportCreate,
    FintracReportResponse,
    RiskAssessmentResponse
)

logger = structlog.get_logger()


class FintracService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_verification(
        self, 
        application_id: UUID, 
        payload: FintracVerificationCreate, 
        verified_by_user_id: UUID
    ) -> FintracVerificationResponse:
        """Create a new FINTRAC identity verification record.
        
        Args:
            application_id: Associated mortgage application
            payload: Verification details
            verified_by_user_id: User performing verification
            
        Returns:
            Created verification record
            
        Raises:
            AppException: Database or encryption error
        """
        logger.info(
            "fintrac_verification_create",
            application_id=str(application_id),
            client_id=str(payload.client_id)
        )
        
        # Encrypt sensitive data
        try:
            encrypted_id_number = encrypt_pii(payload.id_number)
        except Exception as e:
            logger.error("encryption_failed", error=str(e))
            raise AppException("Failed to encrypt ID number")
        
        # Create verification record
        verification = FintracVerification(
            application_id=application_id,
            client_id=payload.client_id,
            verification_method=payload.verification_method,
            id_type=payload.id_type,
            id_number_encrypted=encrypted_id_number,
            id_expiry_date=payload.id_expiry_date,
            id_issuing_province=payload.id_issuing_province,
            verified_by=verified_by_user_id,
            is_pep=payload.is_pep,
            is_hio=payload.is_hio,
            risk_level=payload.risk_level,
            source_of_funds=payload.source_of_funds,
            occupation=payload.occupation,
            employer=payload.employer
        )
        
        try:
            self.db.add(verification)
            await self.db.commit()
            await self.db.refresh(verification)
            
            # Build response with computed field
            response_data = {
                "id": verification.id,
                "application_id": verification.application_id,
                "client_id": verification.client_id,
                "verification_method": verification.verification_method,
                "id_type": verification.id_type,
                "id_expiry_date": verification.id_expiry_date,
                "id_issuing_province": verification.id_issuing_province,
                "verified_by": verification.verified_by,
                "verified_at": verification.verified_at,
                "is_pep": verification.is_pep,
                "is_hio": verification.is_hio,
                "risk_level": verification.risk_level,
                "requires_enhanced_due_diligence": (
                    verification.risk_level == "high" or 
                    verification.is_pep or 
                    verification.is_hio
                ),
                "created_at": verification.created_at
            }
            
            return FintracVerificationResponse(**response_data)
        except Exception as e:
            await self.db.rollback()
            logger.error("db_error", operation="create_verification", error=str(e))
            raise AppException("Failed to create verification record")

    async def get_verification_status(self, application_id: UUID) -> Optional[FintracVerificationResponse]:
        """Get latest verification status for an application.
        
        Args:
            application_id: Mortgage application ID
            
        Returns:
            Latest verification record or None
        """
        logger.info("fintrac_get_verification", application_id=str(application_id))
        
        stmt = (
            select(FintracVerification)
            .where(FintracVerification.application_id == application_id)
            .where(FintracVerification.is_deleted == False)
            .order_by(FintracVerification.created_at.desc())
            .limit(1)
            .options(selectinload(FintracVerification.application))
        )
        
        result = await self.db.execute(stmt)
        verification = result.scalar_one_or_none()
        
        if not verification:
            return None
            
        response_data = {
            "id": verification.id,
            "application_id": verification.application_id,
            "client_id": verification.client_id,
            "verification_method": verification.verification_method,
            "id_type": verification.id_type,
            "id_expiry_date": verification.id_expiry_date,
            "id_issuing_province": verification.id_issuing_province,
            "verified_by": verification.verified_by,
            "verified_at": verification.verified_at,
            "is_pep": verification.is_pep,
            "is_hio": verification.is_hio,
            "risk_level": verification.risk_level,
            "requires_enhanced_due_diligence": (
                verification.risk_level == "high" or 
                verification.is_pep or 
                verification.is_hio
            ),
            "created_at": verification.created_at
        }
        
        return FintracVerificationResponse(**response_data)

    async def create_transaction_report(
        self, 
        application_id: UUID, 
        payload: FintracReportCreate, 
        created_by_user_id: UUID
    ) -> FintracReportResponse:
        """File a FINTRAC transaction report.
        
        Args:
            application_id: Associated mortgage application
            payload: Report details
            created_by_user_id: User filing report
            
        Returns:
            Created report record
        """
        logger.info(
            "fintrac_report_create",
            application_id=str(application_id),
            report_type=payload.report_type,
            amount=float(payload.amount)
        )
        
        # FIXED: Add explicit flag for large transactions (> CAD $10,000)
        if payload.currency == "CAD" and payload.amount > Decimal('10000') and payload.report_type != "large_cash_transaction":
            logger.warning(
                "large_transaction_requires_flag",
                application_id=str(application_id),
                amount=float(payload.amount),
                currency=payload.currency
            )
            raise AppException("Transactions over CAD $10,000 must be filed as large_cash_transaction type")
        
        report = FintracReport(
            application_id=application_id,
            report_type=payload.report_type,
            amount=payload.amount,
            currency=payload.currency,
            report_date=payload.report_date,
            created_by=created_by_user_id
        )
        
        try:
            self.db.add(report)
            await self.db.commit()
            await self.db.refresh(report)
            
            # FIXED: Log all financial transactions for audit trail
            logger.info(
                "fintrac_transaction_logged",
                report_id=report.id,
                application_id=str(application_id),
                report_type=payload.report_type,
                amount=float(payload.amount),
                currency=payload.currency,
                created_by=str(created_by_user_id)
            )
            
            return FintracReportResponse.model_validate(report)
        except Exception as e:
            await self.db.rollback()
            logger.error("db_error", operation="create_transaction_report", error=str(e))
            raise AppException("Failed to create transaction report")

    async def list_reports(
        self, 
        application_id: UUID, 
        limit: int = 100, 
        offset: int = 0
    ) -> List[FintracReportResponse]:
        """List FINTRAC reports for an application with pagination.
        
        Args:
            application_id: Mortgage application ID
            limit: Max results (default/max 100)
            offset: Pagination offset
            
        Returns:
            List of report records
        """
        logger.info(
            "fintrac_list_reports",
            application_id=str(application_id),
            limit=limit,
            offset=offset
        )
        
        stmt = (
            select(FintracReport)
            .where(FintracReport.application_id == application_id)
            .where(FintracReport.is_deleted == False)
            .order_by(FintracReport.created_at.desc())
            .limit(limit)
            .offset(offset)
            .options(selectinload(FintracReport.application))
        )
        
        result = await self.db.execute(stmt)
        reports = result.scalars().all()
        
        return [FintracReportResponse.model_validate(r) for r in reports]

    async def get_risk_assessment(self, client_id: UUID) -> RiskAssessmentResponse:
        """Get client's current risk assessment based on latest verification.
        
        Args:
            client_id: Client identifier
            
        Returns:
            Risk assessment summary
        """
        logger.info("fintrac_get_risk_assessment", client_id=str(client_id))
        
        stmt = (
            select(FintracVerification)
            .where(FintracVerification.client_id == client_id)
            .where(FintracVerification.is_deleted == False)
            .order_by(FintracVerification.created_at.desc())
            .limit(1)
        )
        
        result = await self.db.execute(stmt)
        verification = result.scalar_one_or_none()
        
        if not verification:
            # Default low-risk assessment if no verification exists
            return RiskAssessmentResponse(
                client_id=client_id,
                risk_level="low",
                is_pep=False,
                is_hio=False,
                last_verification_date=None,
                requires_enhanced_due_diligence=False
            )
        
        requires_edd = (
            verification.risk_level == "high" or 
            verification.is_pep or 
            verification.is_hio
        )
        
        return RiskAssessmentResponse(
            client_id=client_id,
            risk_level=verification.risk_level,
            is_pep=verification.is_pep,
            is_hio=verification.is_hio,
            last_verification_date=verification.created_at,
            requires_enhanced_due_diligence=requires_edd
        )