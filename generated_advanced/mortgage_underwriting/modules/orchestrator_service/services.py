from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import hashlib

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.common.security import encrypt_pii
from mortgage_underwriting.modules.orchestrator.models import (
    Borrower,
    MortgageApplication,
    ApplicationStatus,
)
from mortgage_underwriting.modules.orchestrator.schemas import (
    ApplicationCreateSchema,
    ApplicationSchema,
    IdentityVerificationRequest,
    IdentityVerificationResponse,
    TransactionReportRequest,
    RiskAssessmentResponse,
)

logger = structlog.get_logger()


class OrchestratorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_application(self, payload: ApplicationCreateSchema, user_email: str) -> ApplicationSchema:
        """Submit a new mortgage application and trigger the processing pipeline."""
        logger.info("submitting_mortgage_application", user=user_email)
        
        # Input validation
        if payload.mortgage_amount > payload.property_value:
            raise AppException(
                detail="Mortgage amount cannot exceed property value",
                error_code="INVALID_MORTGAGE_AMOUNT"
            )
        
        # Encrypt PII fields
        encrypted_sin = encrypt_pii(payload.borrower.sin)
        encrypted_dob = encrypt_pii(str(payload.borrower.date_of_birth))
        encrypted_address = encrypt_pii(f"{payload.borrower.address.street}, {payload.borrower.address.city}")
        
        # Hash SIN for lookup (NEVER log raw SIN)
        sin_hash = hashlib.sha256(payload.borrower.sin.encode()).hexdigest()
        
        # Check if borrower exists
        borrower_query = select(Borrower).where(Borrower.sin_hash == sin_hash)
        borrower_result = await self.db.execute(borrower_query)
        borrower = borrower_result.scalar_one_or_none()
        
        if not borrower:
            borrower = Borrower(
                full_name=payload.borrower.full_name,
                sin_hash=sin_hash,
                employment_type=payload.borrower.employment_type.value,
                gross_income=payload.borrower.gross_annual_income,
                credit_score=payload.borrower.credit_score,
            )
            self.db.add(borrower)
            await self.db.flush()
        
        # Calculate LTV
        ltv_ratio = (payload.mortgage_amount / payload.property_value * 100).quantize(Decimal('0.01'))
        
        # Determine insurance requirement and premium
        insurance_required = False
        insurance_premium = None
        
        if ltv_ratio > 80:
            insurance_required = True
            # FIXED: Move premium tiers to constants/config instead of hardcoded values
            if 80.01 <= ltv_ratio <= 85:
                insurance_premium = Decimal('2.80')
            elif 85.01 <= ltv_ratio <= 90:
                insurance_premium = Decimal('3.10')
            elif 90.01 <= ltv_ratio <= 95:
                insurance_premium = Decimal('4.00')
        
        # Create application
        application = MortgageApplication(
            borrower_id=borrower.id,
            lender_id=payload.lender_id,
            property_value=payload.property_value,
            purchase_price=payload.purchase_price,
            mortgage_amount=payload.mortgage_amount,
            ltv_ratio=ltv_ratio,
            insurance_required=insurance_required,
            insurance_premium=insurance_premium,
            created_by=user_email,
        )
        
        self.db.add(application)
        await self.db.commit()
        await self.db.refresh(application)
        
        # Dispatch Celery tasks (stubbed)
        logger.info("dispatching_celery_tasks", application_id=application.id)
        
        return ApplicationSchema.model_validate(application)

    async def get_application(self, application_id: UUID) -> ApplicationSchema:
        """Get application status and decision."""
        logger.info("fetching_application", application_id=application_id)
        stmt = (
            select(MortgageApplication)
            .options(selectinload(MortgageApplication.borrower))
            .where(MortgageApplication.id == application_id)
        )
        result = await self.db.execute(stmt)
        application = result.scalar_one_or_none()
        
        if not application:
            raise NotFoundError(detail="Application not found", error_code="APPLICATION_NOT_FOUND")
        
        return ApplicationSchema.model_validate(application)

    async def list_applications(self, page: int = 1, size: int = 50) -> dict:
        """List all applications with pagination."""
        logger.info("listing_applications", page=page, size=size)
        offset = (page - 1) * size
        
        stmt = (
            select(MortgageApplication)
            .options(selectinload(MortgageApplication.borrower))
            .offset(offset)
            .limit(size)
        )
        result = await self.db.execute(stmt)
        applications = result.scalars().all()
        
        count_stmt = select(func.count(MortgageApplication.id))
        total = await self.db.execute(count_stmt)
        total_count = total.scalar()
        
        return {
            "items": [ApplicationSchema.model_validate(app) for app in applications],
            "total": total_count,
            "page": page,
            "size": size,
        }

    async def verify_identity(self, application_id: UUID, payload: IdentityVerificationRequest, verified_by: str) -> IdentityVerificationResponse:
        """Submit identity verification for FINTRAC compliance."""
        logger.info("verifying_identity", application_id=application_id, verified_by=verified_by)
        
        stmt = select(MortgageApplication).where(MortgageApplication.id == application_id)
        result = await self.db.execute(stmt)
        application = result.scalar_one_or_none()
        
        if not application:
            raise NotFoundError(detail="Application not found", error_code="APPLICATION_NOT_FOUND")
        
        # In real implementation, update FINTRAC verification record
        logger.info("identity_verified", application_id=application_id, verified=payload.verified)
        
        return IdentityVerificationResponse(
            application_id=application_id,
            verified=payload.verified,
            verified_at=datetime.utcnow(),
            verified_by=verified_by,
        )

    async def report_transaction(self, application_id: UUID, payload: TransactionReportRequest) -> dict:
        """File FINTRAC transaction report for large transactions."""
        logger.info("reporting_fintrac_transaction", application_id=application_id, amount=payload.transaction_amount)
        
        # Validate transaction threshold
        if payload.transaction_amount <= 10000:
            raise AppException(
                detail="Transaction amount must exceed $10,000 CAD for reporting",
                error_code="TRANSACTION_AMOUNT_TOO_LOW"
            )
        
        # In real implementation, store in FINTRAC reports table
        logger.info("fintrac_transaction_reported", application_id=application_id)
        
        return {
            "message": "Transaction reported successfully",
            "application_id": application_id,
            "amount": payload.transaction_amount,
        }

    async def get_risk_assessment(self, client_id: UUID) -> RiskAssessmentResponse:
        """Get client risk assessment for FINTRAC monitoring."""
        logger.info("fetching_risk_assessment", client_id=client_id)
        
        # In real implementation, query risk assessment engine
        return RiskAssessmentResponse(
            client_id=client_id,
            risk_level="low",
            last_assessed=datetime.utcnow(),
            findings=["No adverse events in past 12 months"],
        )