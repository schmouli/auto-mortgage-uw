from hashlib import sha256
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.common.security import encrypt_pii
from mortgage_underwriting.modules.orchestrator.models import Application, Borrower, Document, FintracVerification
from mortgage_underwriting.modules.orchestrator.schemas import (

    ApplicationSubmitRequest,
    ApplicationSubmitResponse,
    ApplicationResponse,
    DocumentResponse,
    FintracVerificationRequest,
    FintracVerificationResponse,
    FintracTransactionReportRequest,
    RiskAssessmentResponse,
    PaginatedApplicationResponse
)

logger = structlog.get_logger()


class OrchestratorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_application(self, payload: ApplicationSubmitRequest) -> ApplicationSubmitResponse:
        """Submit a new mortgage application with borrower and documents."""
        logger.info("submitting_application", lender_id=payload.lender_id)
        
        # Check for existing active application with same SIN
        sin_hash = sha256(payload.borrower.sin.encode()).hexdigest()
        existing_borrower_query = select(Borrower).where(Borrower.sin_hash == sin_hash)
        result = await self.db.execute(existing_borrower_query)
        existing_borrower = result.scalar_one_or_none()
        
        if existing_borrower:
            active_app_query = select(Application).where(
                Application.borrower_id == existing_borrower.id,
                Application.status.in_(["submitted", "extracting", "evaluating"])
            )
            app_result = await self.db.execute(active_app_query)
            if app_result.scalar_one_or_none():
                logger.warning("duplicate_active_application", sin_hash=sin_hash)
                raise AppException(
                    detail="Borrower already has an active application",
                    error_code="ORCHESTRATOR_003"
                )
        
        # Create or get borrower
        if not existing_borrower:
            sin_encrypted = encrypt_pii(payload.borrower.sin)
            dob_encrypted = encrypt_pii(payload.borrower.date_of_birth.isoformat())
            borrower = Borrower(
                full_name=payload.borrower.full_name,
                sin_hash=sin_hash,
                sin_encrypted=sin_encrypted,
                date_of_birth_encrypted=dob_encrypted,
                employment_type=payload.borrower.employment_type,
                gross_income=payload.borrower.gross_annual_income,
                credit_score=payload.borrower.credit_score
            )
            self.db.add(borrower)
            try:
                await self.db.flush()
            except IntegrityError:
                await self.db.rollback()
                logger.error("borrower_creation_failed", sin_hash=sin_hash)
                raise AppException(
                    detail="Failed to create borrower record",
                    error_code="ORCHESTRATOR_004"
                )
        else:
            borrower = existing_borrower
        
        # Create application
        app_id = str(uuid.uuid4())
        application = Application(
            id=app_id,
            borrower_id=borrower.id,
            lender_id=payload.lender_id,
            property_value=payload.property_value,
            purchase_price=payload.purchase_price,
            mortgage_amount=payload.mortgage_amount
        )
        self.db.add(application)
        
        # Create documents
        documents = []
        for doc_payload in payload.documents:
            # In real implementation, would upload to S3 and store key
            # Here we're just creating a placeholder
            doc_id = str(uuid.uuid4())
            s3_key = f"applications/{app_id}/documents/{doc_id}.pdf"
            document = Document(
                id=doc_id,
                application_id=app_id,
                document_type=doc_payload.document_type.value,
                file_name=doc_payload.file_name,
                s3_key=s3_key
            )
            documents.append(document)
            self.db.add(document)
        
        # Create FINTRAC verification record
        fintrac_verification = FintracVerification(
            application_id=app_id,
            verified=False,
            transaction_reported=False
        )
        self.db.add(fintrac_verification)
        
        try:
            await self.db.commit()
            logger.info("application_submitted", application_id=app_id)
        except Exception as e:
            await self.db.rollback()
            logger.error("application_submission_failed", application_id=app_id, error=str(e))
            raise AppException(
                detail="Failed to submit application",
                error_code="ORCHESTRATOR_005"
            )
        
        return ApplicationSubmitResponse(
            application_id=app_id,
            status=application.status,
            created_at=application.created_at,
            message="Application submitted successfully. Processing initiated."
        )

    async def get_application(self, application_id: str) -> ApplicationResponse:
        """Get application by ID."""
        logger.info("fetching_application", application_id=application_id)
        
        query = select(Application).where(Application.id == application_id)
        result = await self.db.execute(query)
        application = result.scalar_one_or_none()
        
        if not application:
            logger.warning("application_not_found", application_id=application_id)
            raise AppException(
                detail="Application not found",
                error_code="ORCHESTRATOR_006"
            )
            
        return ApplicationResponse.model_validate(application)

    async def list_applications(self, page: int = 1, size: int = 50) -> PaginatedApplicationResponse:
        """List all applications with pagination."""
        logger.info("listing_applications", page=page, size=size)
        
        if size > 100:
            size = 100
            
        offset = (page - 1) * size
        
        # Get total count
        count_query = select(func.count(Application.id))
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()
        
        # Get applications
        query = select(Application).offset(offset).limit(size)
        result = await self.db.execute(query)
        applications = result.scalars().all()
        
        items = [ApplicationResponse.model_validate(app) for app in applications]
        
        return PaginatedApplicationResponse(
            items=items,
            total=total,
            page=page,
            size=size
        )

    async def get_application_documents(self, application_id: str) -> List[DocumentResponse]:
        """Get all documents for an application."""
        logger.info("fetching_application_documents", application_id=application_id)
        
        # Verify application exists
        app_query = select(Application).where(Application.id == application_id)
        app_result = await self.db.execute(app_query)
        if not app_result.scalar_one_or_none():
            logger.warning("application_not_found", application_id=application_id)
            raise AppException(
                detail="Application not found",
                error_code="ORCHESTRATOR_006"
            )
        
        # Get documents
        query = select(Document).where(Document.application_id == application_id)
        result = await self.db.execute(query)
        documents = result.scalars().all()
        
        return [DocumentResponse.model_validate(doc) for doc in documents]

    async def verify_identity(self, application_id: str, payload: FintracVerificationRequest) -> FintracVerificationResponse:
        """Verify borrower identity for FINTRAC compliance."""
        logger.info("verifying_identity", application_id=application_id)
        
        # Get FINTRAC verification record
        query = select(FintracVerification).where(FintracVerification.application_id == application_id)
        result = await self.db.execute(query)
        fintrac_record = result.scalar_one_or_none()
        
        if not fintrac_record:
            logger.warning("fintrac_verification_not_found", application_id=application_id)
            raise AppException(
                detail="FINTRAC verification record not found",
                error_code="ORCHESTRATOR_008"
            )
        
        # Update verification status
        fintrac_record.verified = payload.verified
        await self.db.commit()
        await self.db.refresh(fintrac_record)
        
        logger.info("identity_verified", application_id=application_id, verified=payload.verified)
        return FintracVerificationResponse.model_validate(fintrac_record)

    async def get_fintrac_verification_status(self, application_id: str) -> FintracVerificationResponse:
        """Get FINTRAC verification status."""
        logger.info("fetching_fintrac_verification", application_id=application_id)
        
        query = select(FintracVerification).where(FintracVerification.application_id == application_id)
        result = await self.db.execute(query)
        fintrac_record = result.scalar_one_or_none()
        
        if not fintrac_record:
            logger.warning("fintrac_verification_not_found", application_id=application_id)
            raise AppException(
                detail="FINTRAC verification record not found",
                error_code="ORCHESTRATOR_008"
            )
            
        return FintracVerificationResponse.model_validate(fintrac_record)

    async def report_transaction(self, application_id: str, payload: FintracTransactionReportRequest) -> FintracVerificationResponse:
        """Report a large-value transaction for FINTRAC compliance."""
        logger.info("reporting_transaction", application_id=application_id, amount=float(payload.amount))
        
        # Get FINTRAC verification record
        query = select(FintracVerification).where(FintracVerification.application_id == application_id)
        result = await self.db.execute(query)
        fintrac_record = result.scalar_one_or_none()
        
        if not fintrac_record:
            logger.warning("fintrac_verification_not_found", application_id=application_id)
            raise AppException(
                detail="FINTRAC verification record not found",
                error_code="ORCHESTRATOR_008"
            )
        
        # Update transaction reporting status
        fintrac_record.transaction_reported = True
        await self.db.commit()
        await self.db.refresh(fintrac_record)
        
        logger.info("transaction_reported", application_id=application_id, amount=float(payload.amount))
        return FintracVerificationResponse.model_validate(fintrac_record)

    async def get_risk_assessment(self, client_id: int) -> RiskAssessmentResponse:
        """Get client risk assessment based on historical data."""
        logger.info("fetching_risk_assessment", client_id=client_id)
        
        # In a real implementation, this would query risk assessment tables
        # For now, returning mock data
        return RiskAssessmentResponse(
            client_id=client_id,
            risk_level="low",
            last_assessment_date="2023-06-15T10:30:00Z",
            findings=[
                "No adverse events in past 2 years",
                "Stable employment history",
                "Credit score above threshold"
            ]
        )