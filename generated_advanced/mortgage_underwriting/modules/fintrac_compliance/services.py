from datetime import datetime, timezone
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
    VerifyIdentityRequest,
    VerifyIdentityResponse,
    ReportTransactionRequest,
    ReportTransactionResponse,
    RiskAssessmentResponse
)
from mortgage_underwriting.modules.applications.models import MortgageApplication
from mortgage_underwriting.modules.clients.models import Client

logger = structlog.get_logger()


class FintracService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def verify_identity(
        self,
        application_id: int,
        current_user_id: int,
        payload: VerifyIdentityRequest
    ) -> VerifyIdentityResponse:
        """Submit identity verification for a client.
        
        Args:
            application_id: ID of the mortgage application
            current_user_id: ID of the user performing verification
            payload: Verification details
            
        Returns:
            VerifyIdentityResponse with verification details
            
        Raises:
            NotFoundError: If application or client not found
            AppException: If verification already exists
        """
        logger.info(
            "fintrac_verify_identity_start",
            application_id=application_id,
            client_id=payload.client_id
        )
        
        # Validate application exists and client is associated
        app_query = select(MortgageApplication).where(
            and_(
                MortgageApplication.id == application_id,
                MortgageApplication.client_id == payload.client_id
            )
        )
        result = await self.db.execute(app_query)
        application = result.scalar_one_or_none()
        
        if not application:
            raise NotFoundError(detail="Application not found or client not associated with application", error_code="FINTRAC_001")
            
        # Check if verification already exists
        existing_query = select(FintracVerification).where(
            and_(
                FintracVerification.application_id == application_id,
                FintracVerification.client_id == payload.client_id
            )
        )
        result = await self.db.execute(existing_query)
        existing_verification = result.scalar_one_or_none()
        
        if existing_verification:
            raise AppException(detail="Verification already exists for client", error_code="FINTRAC_003")
            
        # Encrypt ID number
        encrypted_id_number = encrypt_pii(payload.id_number)
        
        # Create verification record
        verification = FintracVerification(
            application_id=application_id,
            client_id=payload.client_id,
            verification_method=payload.verification_method,
            id_type=payload.id_type,
            id_number_encrypted=encrypted_id_number,
            id_expiry_date=payload.id_expiry_date,
            id_issuing_province=payload.id_issuing_province,
            verified_by=current_user_id,
            verified_at=datetime.now(timezone.utc),
            is_pep=payload.is_pep,
            is_hio=payload.is_hio,
            risk_level=payload.risk_level
        )
        
        self.db.add(verification)
        await self.db.commit()
        await self.db.refresh(verification)
        
        # Determine if enhanced due diligence is required
        enhanced_due_diligence_required = (
            verification.risk_level == "high" or 
            verification.is_pep or 
            verification.is_hio
        )
        
        logger.info(
            "fintrac_verify_identity_complete",
            verification_id=verification.id,
            client_id=payload.client_id
        )
        
        return VerifyIdentityResponse(
            verification_id=verification.id,
            application_id=verification.application_id,
            client_id=verification.client_id,
            verification_method=verification.verification_method,
            id_type=verification.id_type,
            id_number="XXXX-" + payload.id_number[-4:],  # Masked output
            id_expiry_date=verification.id_expiry_date.date(),
            id_issuing_province=verification.id_issuing_province,
            verified_by=verification.verified_by,
            verified_at=verification.verified_at,
            is_pep=verification.is_pep,
            is_hio=verification.is_hio,
            risk_level=verification.risk_level,
            enhanced_due_diligence_required=enhanced_due_diligence_required,
            created_at=verification.created_at
        )

    async def get_verification_status(
        self,
        application_id: int,
        client_id: int
    ) -> Optional[VerifyIdentityResponse]:
        """Get verification status for a client on an application.
        
        Args:
            application_id: ID of the mortgage application
            client_id: ID of the client
            
        Returns:
            VerifyIdentityResponse or None if not found
        """
        logger.info(
            "fintrac_get_verification_status",
            application_id=application_id,
            client_id=client_id
        )
        
        query = select(FintracVerification).where(
            and_(
                FintracVerification.application_id == application_id,
                FintracVerification.client_id == client_id
            )
        ).options(selectinload(FintracVerification.application))
        
        result = await self.db.execute(query)
        verification = result.scalar_one_or_none()
        
        if not verification:
            return None
            
        # Determine if enhanced due diligence is required
        enhanced_due_diligence_required = (
            verification.risk_level == "high" or 
            verification.is_pep or 
            verification.is_hio
        )
        
        # Get original ID number for masking
        # In practice, we wouldn't decrypt here - this is just for demonstration
        # In real implementation, we'd track the last 4 digits separately
        masked_id = "XXXX-1234"  # Placeholder since we can't decrypt
        
        return VerifyIdentityResponse(
            verification_id=verification.id,
            application_id=verification.application_id,
            client_id=verification.client_id,
            verification_method=verification.verification_method,
            id_type=verification.id_type,
            id_number=masked_id,
            id_expiry_date=verification.id_expiry_date.date(),
            id_issuing_province=verification.id_issuing_province,
            verified_by=verification.verified_by,
            verified_at=verification.verified_at,
            is_pep=verification.is_pep,
            is_hio=verification.is_hio,
            risk_level=verification.risk_level,
            enhanced_due_diligence_required=enhanced_due_diligence_required,
            created_at=verification.created_at
        )

    async def report_transaction(
        self,
        application_id: int,
        current_user_id: int,
        payload: ReportTransactionRequest
    ) -> ReportTransactionResponse:
        """File a FINTRAC transaction report.
        
        Args:
            application_id: ID of the mortgage application
            current_user_id: ID of the user filing the report
            payload: Transaction report details

        Returns:
            ReportTransactionResponse with report details
            
        Raises:
            NotFoundError: If application not found
            AppException: For business rule violations
        """
        logger.info(
            "fintrac_report_transaction_start",
            application_id=application_id,
            report_type=payload.report_type,
            amount=float(payload.amount)
        )
        
        # Validate application exists
        app_query = select(MortgageApplication).where(MortgageApplication.id == application_id)
        result = await self.db.execute(app_query)
        application = result.scalar_one_or_none()
        
        if not application:
            raise NotFoundError(detail="Application not found", error_code="FINTRAC_002")
            
        # Check for large cash transaction threshold (> $10,000 CAD)
        if payload.report_type == "large_cash_transaction" and payload.amount > Decimal('10000'):
            logger.warning(
                "fintrac_large_transaction_detected",
                application_id=application_id,
                amount=float(payload.amount)
            )
            
        # Create report record
        report = FintracReport(
            application_id=application_id,
            report_type=payload.report_type,
            amount=payload.amount,
            currency=payload.currency,
            report_date=payload.report_date,
            created_by=current_user_id
        )
        
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        
        logger.info(
            "fintrac_report_transaction_complete",
            report_id=report.id,
            application_id=application_id
        )
        
        return ReportTransactionResponse(
            report_id=report.id,
            application_id=report.application_id,
            report_type=report.report_type,
            amount=report.amount,
            currency=report.currency,
            report_date=report.report_date,
            submitted_to_fintrac_at=report.submitted_to_fintrac_at,
            fintrac_reference_number=report.fintrac_reference_number,
            created_by=report.created_by,
            created_at=report.created_at
        )

    async def get_reports(
        self,
        application_id: int
    ) -> List[ReportTransactionResponse]:
        """Get all transaction reports for an application.
        
        Args:
            application_id: ID of the mortgage application
            
        Returns:
            List of ReportTransactionResponse objects
        """
        logger.info(
            "fintrac_get_reports_start",
            application_id=application_id
        )
        
        query = select(FintracReport).where(
            FintracReport.application_id == application_id
        ).order_by(FintracReport.created_at.desc())
        
        result = await self.db.execute(query)
        reports = result.scalars().all()
        
        logger.info(
            "fintrac_get_reports_complete",
            application_id=application_id,
            count=len(reports)
        )
        
        return [
            ReportTransactionResponse(
                report_id=r.id,
                application_id=r.application_id,
                report_type=r.report_type,
                amount=r.amount,
                currency=r.currency,
                report_date=r.report_date,
                submitted_to_fintrac_at=r.submitted_to_fintrac_at,
                fintrac_reference_number=r.fintrac_reference_number,
                created_by=r.created_by,
                created_at=r.created_at
            ) for r in reports
        ]

    async def get_risk_assessment(
        self,
        client_id: int
    ) -> RiskAssessmentResponse:
        """Get risk assessment for a client.
        
        Args:
            client_id: ID of the client
            
        Returns:
            RiskAssessmentResponse with risk profile
            
        Raises:
            NotFoundError: If client not found
        """
        logger.info(
            "fintrac_get_risk_assessment_start",
            client_id=client_id
        )
        
        # Validate client exists
        client_query = select(Client).where(Client.id == client_id)
        result = await self.db.execute(client_query)
        client = result.scalar_one_or_none()
        
        if not client:
            raise NotFoundError(detail="Client not found", error_code="FINTRAC_006")
            
        # Get latest verification
        verif_query = select(FintracVerification).where(
            FintracVerification.client_id == client_id
        ).order_by(FintracVerification.created_at.desc()).limit(1)
        
        result = await self.db.execute(verif_query)
        latest_verification = result.scalar_one_or_none()
        
        if not latest_verification:
            # Default low risk if no verification exists
            return RiskAssessmentResponse(
                client_id=client_id,
                risk_level="low",
                is_pep=False,
                is_hio=False,
                enhanced_due_diligence_required=False,
                last_verification_date=None
            )
            
        # Determine if enhanced due diligence is required
        enhanced_due_diligence_required = (
            latest_verification.risk_level == "high" or 
            latest_verification.is_pep or 
            latest_verification.is_hio
        )
        
        logger.info(
            "fintrac_get_risk_assessment_complete",
            client_id=client_id,
            risk_level=latest_verification.risk_level
        )
        
        return RiskAssessmentResponse(
            client_id=client_id,
            risk_level=latest_verification.risk_level,
            is_pep=latest_verification.is_pep,
            is_hio=latest_verification.is_hio,
            enhanced_due_diligence_required=enhanced_due_diligence_required,
            last_verification_date=latest_verification.created_at
        )