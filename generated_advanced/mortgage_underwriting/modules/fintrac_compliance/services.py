from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from sqlalchemy import select, and_
import structlog
from mortgage_underwriting.common.exceptions import NotFoundError
from mortgage_underwriting.common.security import encrypt_pii
from mortgage_underwriting.modules.fintrac.models import FintracVerification, FintracReport
from mortgage_underwriting.modules.fintrac.schemas import (
    FintracVerificationRequest,
    FintracTransactionReportRequest,
    FintracVerificationResponse,
    FintracVerificationStatusResponse,
    FintracReportListResponse,
    FintracRiskAssessmentResponse
)
from mortgage_underwriting.modules.application.models import MortgageApplication, Client

logger = structlog.get_logger()


class FintracComplianceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def verify_identity(
        self, 
        application_id: int, 
        payload: FintracVerificationRequest,
        created_by: int
    ) -> FintracVerificationResponse:
        """Submit identity verification for a client.
        
        Args:
            application_id: ID of the mortgage application
            payload: Verification details
            created_by: User ID who created the record
            
        Returns:
            FintracVerificationResponse with verification details
            
        Raises:
            NotFoundError: If application or client not found
            AppException: If verification already exists
        """
        logger.info(
            "fintrac_verify_identity_start",
            application_id=application_id,
            client_id=payload.client_id
        )
        
        # Check if application exists
        app_query = select(MortgageApplication).where(MortgageApplication.id == application_id)
        app_result = await self.db.execute(app_query)
        application = app_result.scalar_one_or_none()
        
        if not application:
            logger.error("fintrac_application_not_found", application_id=application_id)
            raise NotFoundError(detail="Application not found", error_code="FINTRAC_001")
            
        # Check if client exists
        client_query = select(Client).where(Client.id == payload.client_id)
        client_result = await self.db.execute(client_query)
        client = client_result.scalar_one_or_none()
        
        if not client:
            logger.error("fintrac_client_not_found", client_id=payload.client_id)
            raise NotFoundError(detail="Client not found", error_code="FINTRAC_001")
            
        # Check for recent duplicate verification
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        duplicate_query = select(FintracVerification).where(
            and_(
                FintracVerification.client_id == payload.client_id,
                FintracVerification.created_at >= five_minutes_ago,
                FintracVerification.is_deleted == False
            )
        )
        duplicate_result = await self.db.execute(duplicate_query)
        existing_verification = duplicate_result.scalar_one_or_none()
        
        if existing_verification:
            logger.info(
                "fintrac_duplicate_verification_found",
                verification_id=existing_verification.id
            )
            return FintracVerificationResponse(
                id=existing_verification.id,
                verification_method=existing_verification.verification_method,
                risk_level=existing_verification.risk_level,
                verified_at=existing_verification.verified_at
            )
        
        # Determine risk level
        risk_level = "low"
        if payload.is_pep or payload.is_hio:
            risk_level = "high"
            
        # Encrypt ID number
        encrypted_id = encrypt_pii(payload.id_number)
        
        # Add 5-year retention period
        retention_expires = datetime.utcnow() + timedelta(days=5*365)
        
        # Create verification record
        verification = FintracVerification(
            application_id=application_id,
            client_id=payload.client_id,
            verification_method=payload.verification_method,
            id_type=payload.id_type,
            id_number_encrypted=encrypted_id,
            id_expiry_date=payload.id_expiry_date,
            id_issuing_province=payload.id_issuing_province,
            is_pep=payload.is_pep,
            is_hio=payload.is_hio,
            risk_level=risk_level,
            retention_expires_at=retention_expires,
            created_by=created_by
        )
        
        self.db.add(verification)
        await self.db.commit()
        await self.db.refresh(verification)
        
        logger.info(
            "fintrac_verification_created",
            verification_id=verification.id,
            client_id=payload.client_id
        )
        
        return FintracVerificationResponse(
            id=verification.id,
            verification_method=verification.verification_method,
            risk_level=verification.risk_level,
            verified_at=verification.verified_at
        )

    async def get_verification_status(self, application_id: int) -> List[FintracVerificationStatusResponse]:
        """Get verification status for an application.
        
        Args:
            application_id: ID of the mortgage application
            
        Returns:
            List of verification statuses
        """
        logger.info("fintrac_get_verification_status", application_id=application_id)
        
        query = select(FintracVerification).where(
            and_(
                FintracVerification.application_id == application_id,
                FintracVerification.is_deleted == False
            )
        ).order_by(FintracVerification.created_at.desc())
        
        result = await self.db.execute(query)
        verifications = result.scalars().all()
        
        return [
            FintracVerificationStatusResponse.model_validate(v) 
            for v in verifications
        ]

    async def report_transaction(
        self, 
        application_id: int, 
        payload: FintracTransactionReportRequest,
        created_by: int
    ) -> FintracReportListResponse:
        """File a FINTRAC transaction report.
        
        Args:
            application_id: ID of the mortgage application
            payload: Transaction report details
            created_by: User ID who created the record
            
        Returns:
            Created report details
        """
        logger.info(
            "fintrac_report_transaction_start",
            application_id=application_id,
            report_type=payload.report_type,
            amount=payload.amount
        )
        
        # Check if application exists
        app_query = select(MortgageApplication).where(MortgageApplication.id == application_id)
        app_result = await self.db.execute(app_query)
        application = app_result.scalar_one_or_none()
        
        if not application:
            logger.error("fintrac_application_not_found", application_id=application_id)
            raise NotFoundError(detail="Application not found", error_code="FINTRAC_001")
        
        # Determine if large transaction flag is needed
        is_large_transaction = payload.amount > Decimal('10000')
        
        # Add 5-year retention period
        retention_expires = datetime.utcnow() + timedelta(days=5*365)
        
        # Create report record
        report = FintracReport(
            application_id=application_id,
            report_type=payload.report_type,
            amount=payload.amount,
            currency=payload.currency,
            is_large_transaction_flag=is_large_transaction,
            created_by=created_by,
            retention_expires_at=retention_expires
        )
        
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        
        logger.info(
            "fintrac_report_created",
            report_id=report.id,
            report_type=payload.report_type
        )
        
        return FintracReportListResponse.model_validate(report)

    async def list_reports(self, application_id: int) -> List[FintracReportListResponse]:
        """List all FINTRAC reports for an application.
        
        Args:
            application_id: ID of the mortgage application
            
        Returns:
            List of reports
        """
        logger.info("fintrac_list_reports", application_id=application_id)
        
        query = select(FintracReport).where(
            and_(
                FintracReport.application_id == application_id,
                FintracReport.is_deleted == False
            )
        ).order_by(FintracReport.created_at.desc())
        
        result = await self.db.execute(query)
        reports = result.scalars().all()
        
        return [
            FintracReportListResponse.model_validate(r) 
            for r in reports
        ]

    async def get_risk_assessment(self, client_id: int) -> FintracRiskAssessmentResponse:
        """Get risk assessment for a client.
        
        Args:
            client_id: ID of the client
            
        Returns:
            Risk assessment details
            
        Raises:
            NotFoundError: If client not found
        """
        logger.info("fintrac_get_risk_assessment", client_id=client_id)
        
        # Get latest verification for client
        verification_query = select(FintracVerification).where(
            and_(
                FintracVerification.client_id == client_id,
                FintracVerification.is_deleted == False
            )
        ).order_by(FintracVerification.created_at.desc()).limit(1)
        
        verification_result = await self.db.execute(verification_query)
        verification = verification_result.scalar_one_or_none()
        
        if not verification:
            logger.error("fintrac_client_verification_not_found", client_id=client_id)
            raise NotFoundError(detail="No verification found for client", error_code="FINTRAC_005")
        
        # Determine enhanced due diligence requirement
        requires_edd = verification.risk_level == "high" or verification.is_pep or verification.is_hio
        
        return FintracRiskAssessmentResponse(
            client_id=client_id,
            risk_level=verification.risk_level,
            is_pep=verification.is_pep,
            is_hio=verification.is_hio,
            requires_enhanced_due_diligence=requires_edd,
            last_verified_at=verification.record_created_at
        )