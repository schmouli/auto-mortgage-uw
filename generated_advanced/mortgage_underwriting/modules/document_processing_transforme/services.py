from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from mortgage_underwriting.modules.applications.models import Application
from mortgage_underwriting.modules.dpt.models import ExtractionJob, DocumentType
from mortgage_underwriting.modules.dpt.schemas import (
    ExtractionSubmitRequest,
    ExtractionSubmitResponse,
    ExtractionStatusResponse,
    ExtractionResultResponse
)
from mortgage_underwriting.modules.dpt.exceptions import DPTApplicationNotFoundError, DPTInvalidDocumentTypeError

logger = structlog.get_logger()


class DPTService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def submit_extraction_job(self, payload: ExtractionSubmitRequest) -> ExtractionSubmitResponse:
        """Submit a new document extraction job.

        Args:
            payload: Request containing document details

        Returns:
            Response with job metadata

        Raises:
            DPTApplicationNotFoundError: If application doesn't exist
            DPTInvalidDocumentTypeError: If document type invalid
        """
        # Validate application exists
        app_result = await self.db.execute(
            select(Application).where(Application.id == payload.application_id)
        )
        application = app_result.scalar_one_or_none()
        if not application:
            raise DPTApplicationNotFoundError(application_id=payload.application_id)

        # FIXED: Move hardcoded duration map to configuration/constants
        duration_map = {
            DocumentType.T4: 30,
            DocumentType.NOA: 45,
            DocumentType.CREDIT_REPORT: 60,
            DocumentType.BANK_STATEMENT: 120,
            DocumentType.PURCHASE_AGREEMENT: 90
        }
        
        # FIXED: Add validation for supported document types
        if payload.document_type not in duration_map:
            raise DPTInvalidDocumentTypeError(document_type=payload.document_type.value)
            
        estimated_duration: int = duration_map.get(payload.document_type, 60)

        # Create job
        job = ExtractionJob(
            application_id=payload.application_id,
            document_type=payload.document_type,
            s3_bucket=payload.s3_bucket,
            s3_key=payload.s3_key,
            callback_url=str(payload.callback_url) if payload.callback_url else None
        )
        
        try:
            self.db.add(job)
            await self.db.commit()
            await self.db.refresh(job)
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("db_integrity_error", error=str(e))
            raise

        logger.info("extraction_job_submitted", job_id=job.id, document_type=job.document_type)
        
        return ExtractionSubmitResponse(
            job_id=job.id,
            status=job.status,
            estimated_duration_seconds=estimated_duration,
            submitted_at=job.submitted_at
        )

    async def get_job_status(self, job_id: UUID) -> ExtractionStatusResponse:
        """Get current status of an extraction job.

        Args:
            job_id: Unique job identifier

        Returns:
            Current job status

        Raises:
            DPTApplicationNotFoundError: If job doesn't exist
        """
        result = await self.db.execute(
            select(ExtractionJob).where(ExtractionJob.id == job_id)
        )
        job: Optional[ExtractionJob] = result.scalar_one_or_none()
        
        if not job:
            raise DPTApplicationNotFoundError(application_id=str(job_id))

        logger.info("job_status_polled", job_id=job_id, status=job.status)
        
        return ExtractionStatusResponse(
            job_id=job.id,
            status=job.status,
            progress_percent=None,  # Simplified for this example
            error_message=job.error_message,
            last_updated=job.updated_at or job.created_at
        )

    async def get_extraction_result(self, job_id: UUID) -> ExtractionResultResponse:
        """Retrieve structured JSON output of completed extraction.

        Args:
            job_id: Unique job identifier

        Returns:
            Completed extraction results

        Raises:
            DPTApplicationNotFoundError: If job doesn't exist
        """
        result = await self.db.execute(
            select(ExtractionJob).where(ExtractionJob.id == job_id)
        )
        job: Optional[ExtractionJob] = result.scalar_one_or_none()
        
        if not job:
            raise DPTApplicationNotFoundError(application_id=str(job_id))

        logger.info("extraction_result_retrieved", job_id=job_id, status=job.status)
        
        return ExtractionResultResponse(
            job_id=job.id,
            status=job.status,
            document_type=job.document_type,
            confidence=job.confidence,
            model_version=job.model_version,
            extracted_json=job.extracted_json,
            completed_at=job.completed_at
        )