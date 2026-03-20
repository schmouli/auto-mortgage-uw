from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from mortgage_underwriting.modules.dpt.models import ExtractionJob
from mortgage_underwriting.modules.dpt.schemas import (
    ExtractionSubmitRequest,
    ExtractionSubmitResponse,
    ExtractionStatusResponse,
    ExtractionResultResponse,
)
from mortgage_underwriting.modules.dpt.exceptions import (
    DPTInvalidInputError,
    DPTDocumentAlreadySubmittedError,
    DPTJobNotFoundError,
)

logger = structlog.get_logger()


class DPTService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_extraction_job(self, payload: ExtractionSubmitRequest) -> ExtractionSubmitResponse:
        """Submit a new document for extraction.
        
        Args:
            payload: Document submission details
            
        Returns:
            Response with job metadata
            
        Raises:
            DPTInvalidInputError: Invalid input parameters
            DPTDocumentAlreadySubmittedError: Duplicate submission
        """
        # Check for duplicate submissions
        stmt = select(ExtractionJob).where(
            ExtractionJob.application_id == payload.application_id,
            ExtractionJob.document_type == payload.document_type
        )
        result = await self.db.execute(stmt)
        existing_job = result.scalar_one_or_none()
        
        if existing_job:
            logger.warning(
                "duplicate_extraction_submission",
                application_id=payload.application_id,
                document_type=payload.document_type,
                existing_job_id=existing_job.id
            )
            raise DPTDocumentAlreadySubmittedError(
                f"Document of type '{payload.document_type}' already submitted for application {payload.application_id}"
            )
        
        # Create new job
        job_id = str(uuid.uuid4())
        job = ExtractionJob(
            id=job_id,
            application_id=payload.application_id,
            document_type=payload.document_type.value,
            s3_key=payload.s3_key,
            priority=payload.priority
        )
        
        try:
            self.db.add(job)
            await self.db.commit()
            await self.db.refresh(job)
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("failed_to_create_job", error=str(e))
            raise DPTInvalidInputError("Failed to create extraction job due to data integrity issues")
        
        # Estimate processing time based on priority (placeholder logic)
        estimated_time = max(10, 60 - (payload.priority * 5))
        
        logger.info(
            "extraction_job_submitted",
            job_id=job_id,
            application_id=payload.application_id,
            document_type=payload.document_type
        )
        
        return ExtractionSubmitResponse(
            job_id=job_id,
            status="queued",
            estimated_processing_time_seconds=estimated_time,
            created_at=job.created_at
        )

    async def get_job_status(self, job_id: str) -> ExtractionStatusResponse:
        """Get the current status of an extraction job.
        
        Args:
            job_id: UUID of the job
            
        Returns:
            Current job status information
            
        Raises:
            DPTJobNotFoundError: Job does not exist
        """
        stmt = select(ExtractionJob).where(ExtractionJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            logger.warning("job_not_found", job_id=job_id)
            raise DPTJobNotFoundError(f"Extraction job with ID {job_id} not found")
        
        return ExtractionStatusResponse(
            job_id=job.id,
            status=job.status,
            document_type=job.document_type,
            confidence=job.confidence,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_code=job.error_code,
            error_detail=job.error_detail
        )

    async def get_extraction_result(self, job_id: str) -> ExtractionResultResponse:
        """Retrieve the results of a completed extraction job.
        
        Args:
            job_id: UUID of the job
            
        Returns:
            Structured extraction results
            
        Raises:
            DPTJobNotFoundError: Job does not exist
        """
        stmt = select(ExtractionJob).where(ExtractionJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            logger.warning("job_not_found", job_id=job_id)
            raise DPTJobNotFoundError(f"Extraction job with ID {job_id} not found")
        
        if job.status != "completed":
            logger.warning("job_not_completed", job_id=job_id, status=job.status)
            raise DPTJobNotFoundError(f"Extraction job {job_id} is not yet completed (status: {job.status})")
        
        return ExtractionResultResponse(
            job_id=job.id,
            document_type=job.document_type,
            confidence=job.confidence,
            model_version=job.model_version,
            extracted_json=job.extracted_json or {},
            created_at=job.created_at,
            completed_at=job.completed_at
        )