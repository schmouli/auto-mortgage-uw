from decimal import Decimal
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional, Tuple
import json
import uuid

from sqlalchemy import select, func as sql_func
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.common.security import encrypt_pii, hash_value
from mortgage_underwriting.modules.orchestrator.models import Application, Borrower, Document, FINTRACReport, ApplicationStatus
from mortgage_underwriting.modules.orchestrator.schemas import (
    ApplicationCreateRequest, BorrowerInfo, FINTRACIdentityVerifyRequest,
    FINTRACReportTransactionRequest, RiskAssessmentResponse, ReprocessRequest
)

logger = structlog.get_logger()

class OrchestratorService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def submit_application(
        self, 
        payload: ApplicationCreateRequest,
        documents: List[Dict[str, Any]]
    ) -> Tuple[Application, str]:
        """Submit a new mortgage application and initiate processing pipeline."""
        correlation_id = str(uuid.uuid4())
        logger.info("orchestrator_submit_application_start", correlation_id=correlation_id)

        try:
            # Parse and validate borrower info
            borrower_data = json.loads(payload.borrower_json)
            borrower_info = BorrowerInfo(**borrower_data)

            # Encrypt PII
            sin_encrypted = encrypt_pii(borrower_info.sin)
            dob_encrypted = encrypt_pii(borrower_info.date_of_birth)
            sin_hash = hash_value(borrower_info.sin)

            # Check if borrower exists
            stmt = select(Borrower).where(Borrower.sin_hash == sin_hash)
            result = await self.db.execute(stmt)
            existing_borrower = result.scalar_one_or_none()

            if existing_borrower:
                borrower = existing_borrower
                logger.info("orchestrator_borrower_found", borrower_id=borrower.id)
            else:
                borrower = Borrower(
                    id=uuid.uuid4(),
                    full_name=borrower_info.full_name,
                    sin_hash=sin_hash,
                    sin_encrypted=sin_encrypted,
                    dob_encrypted=dob_encrypted,
                    employment_type=borrower_info.employment_type,
                    gross_annual_income=borrower_info.gross_annual_income,
                    monthly_liability_payments=borrower_info.monthly_liability_payments or Decimal('0.00'),
                    credit_score=borrower_info.credit_score
                )
                self.db.add(borrower)
                await self.db.flush()
                logger.info("orchestrator_borrower_created", borrower_id=borrower.id)

            # Create application
            application = Application(
                id=uuid.uuid4(),
                borrower_id=borrower.id,
                lender_id=payload.lender_id,
                property_value=payload.property_value,
                purchase_price=payload.purchase_price,
                mortgage_amount=payload.mortgage_amount,
                contract_interest_rate=payload.contract_interest_rate,
                status=ApplicationStatus.SUBMITTED
            )
            self.db.add(application)
            await self.db.flush()

            # Save document references
            doc_instances = []
            for doc in documents:
                doc_instance = Document(
                    id=uuid.uuid4(),
                    application_id=application.id,
                    document_type=doc['type'],
                    s3_key=doc['s3_key'],
                    file_size=doc['size'],
                    mime_type=doc['mime_type']
                )
                doc_instances.append(doc_instance)
                self.db.add(doc_instance)
            
            await self.db.commit()
            logger.info("orchestrator_application_submitted", application_id=application.id)

            # Simulate dispatching Celery task
            celery_task_id = str(uuid.uuid4())
            logger.info("orchestrator_celery_task_dispatched", task_id=celery_task_id, application_id=application.id)
            
            return application, celery_task_id

        except Exception as e:
            await self.db.rollback()
            logger.error("orchestrator_submit_application_failed", error=str(e), correlation_id=correlation_id)
            raise AppException(f"Failed to submit application: {str(e)}") from e

    async def get_application_status(self, application_id: UUID) -> Application:
        """Get detailed status of an application."""
        logger.info("orchestrator_get_application_status", application_id=application_id)
        stmt = select(Application).options(
            selectinload(Application.borrower),
            selectinload(Application.documents)
        ).where(Application.id == application_id)
        
        result = await self.db.execute(stmt)
        app = result.scalar_one_or_none()
        
        if not app:
            raise NotFoundError(f"Application {application_id} not found")
            
        return app

    async def list_applications(self, page: int = 1, size: int = 20) -> Tuple[List[Application], int, int, int]:
        """List applications with pagination."""
        if size > 100:
            size = 100
        offset = (page - 1) * size
        
        logger.info("orchestrator_list_applications", page=page, size=size)
        
        # Count total
        count_stmt = select(sql_func.count(Application.id))
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar_one()
        
        # Fetch paginated results
        stmt = select(Application).order_by(Application.created_at.desc()).offset(offset).limit(size)
        result = await self.db.execute(stmt)
        apps = result.scalars().all()
        
        return apps, total, page, size

    async def get_documents(self, application_id: UUID) -> List[Document]:
        """List all documents for an application."""
        logger.info("orchestrator_get_documents", application_id=application_id)
        stmt = select(Document).where(Document.application_id == application_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def verify_identity(self, application_id: UUID, payload: FINTRACIdentityVerifyRequest) -> FINTRACReport:
        """Record identity verification for FINTRAC compliance."""
        logger.info("orchestrator_verify_identity", application_id=application_id)
        
        # Get application to ensure it exists and fetch borrower_id
        app_stmt = select(Application).where(Application.id == application_id)
        app_result = await self.db.execute(app_stmt)
        application = app_result.scalar_one_or_none()
        
        if not application:
            raise NotFoundError(f"Application {application_id} not found")
        
        # In a real implementation, we'd check the application exists
        # Here we just create a record
        report = FINTRACReport(
            id=uuid.uuid4(),
            application_id=application_id,
            client_id=application.borrower_id,  # Fixed: Use actual borrower_id from application
            transaction_type="identity_verification",
            amount=Decimal('0.00'),
            currency="CAD",
            is_high_risk=False,
            verification_status="verified",
            report_data={
                "method": payload.verification_method,
                "timestamp": payload.verification_timestamp.isoformat(),
                "verifier_id": payload.verifier_id
            }
        )
        
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        
        return report

    async def report_fintrac_transaction(self, application_id: UUID, payload: FINTRACReportTransactionRequest) -> FINTRACReport:
        """Record a financial transaction for FINTRAC reporting."""
        logger.info("orchestrator_report_fintrac_transaction", application_id=application_id)
        
        # Verify application exists
        app_stmt = select(Application).where(Application.id == application_id)
        app_result = await self.db.execute(app_stmt)
        application = app_result.scalar_one_or_none()
        
        if not application:
            raise NotFoundError(f"Application {application_id} not found")
        
        # Create FINTRAC report
        report = FINTRACReport(
            id=uuid.uuid4(),
            application_id=application_id,
            client_id=application.borrower_id,
            transaction_type=payload.transaction_type,
            amount=payload.amount,
            currency=payload.currency,
            is_high_risk=payload.is_high_risk,
            verification_status="pending",
            report_data=payload.report_data
        )
        
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        
        # Log large transactions (>CAD $10,000)
        if payload.amount > Decimal('10000') and payload.currency == "CAD":
            logger.warning(
                "orchestrator_large_transaction_detected",
                application_id=application_id,
                amount=float(payload.amount),
                transaction_type=payload.transaction_type
            )
        
        return report

    async def get_risk_assessment(self, client_id: UUID) -> RiskAssessmentResponse:
        """Get risk assessment for a client."""
        logger.info("orchestrator_get_risk_assessment", client_id=client_id)
        
        # In a real implementation, this would calculate based on borrower/application data
        # This is a mock implementation
        return RiskAssessmentResponse(
            client_id=client_id,
            risk_level="medium",
            last_assessment_date=datetime.utcnow(),
            factors=["credit_score", "debt_to_income_ratio", "employment_stability"],
            overall_score=75
        )

    async def reprocess_application(self, application_id: UUID, force: bool = False) -> str:
        """Trigger reprocessing of an application."""
        logger.info("orchestrator_reprocess_application", application_id=application_id, force=force)
        
        # Verify application exists
        app_stmt = select(Application).where(Application.id == application_id)
        app_result = await self.db.execute(app_stmt)
        application = app_result.scalar_one_or_none()
        
        if not application:
            raise NotFoundError(f"Application {application_id} not found")
        
        # Reset status to trigger reprocessing
        application.status = ApplicationStatus.SUBMITTED
        await self.db.commit()
        
        # Simulate dispatching Celery task
        celery_task_id = str(uuid.uuid4())
        logger.info("orchestrator_reprocess_celery_task_dispatched", task_id=celery_task_id, application_id=application_id)
        
        return celery_task_id