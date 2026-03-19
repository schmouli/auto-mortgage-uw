from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from mortgage_underwriting.common.exceptions import NotFoundError
from mortgage_underwriting.modules.dpt_service.models import Extraction, ExtractionStatusEnum
from mortgage_underwriting.modules.dpt_service.schemas import ExtractRequest, ExtractResponse, JobStatusResponse, ExtractionResultResponse

logger = structlog.get_logger()


class DPTService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def submit_extraction_job(self, payload: ExtractRequest) -> ExtractResponse:
        """Submit a new PDF document for extraction.

        Args:
            payload: Extract request containing document details

        Returns:
            Response with job ID and initial status
        """
        logger.info(
            "submitting_extraction_job",
            application_id=payload.application_id,
            document_type=payload.document_type.value,
            s3_key=payload.s3_key
        )

        # Create extraction record
        extraction = Extraction(
            application_id=payload.application_id,
            document_type=payload.document_type.value,
            s3_key=payload.s3_key,
            filename=payload.filename,
            status=ExtractionStatusEnum.PENDING,
            estimated_processing_time_seconds=30  # Default estimate
        )
        
        self.db.add(extraction)
        await self.db.commit()
        await self.db.refresh(extraction)

        return ExtractResponse(
            job_id=extraction.id,
            status=extraction.status.value,
            estimated_processing_time_seconds=extraction.estimated_processing_time_seconds,
            created_at=extraction.created_at
        )

    async def get_job_status(self, job_id: int) -> JobStatusResponse:
        """Get the current status of an extraction job.

        Args:
            job_id: ID of the extraction job

        Returns:
            Current job status information

        Raises:
            NotFoundError: If job doesn't exist
        """
        logger.info("getting_job_status", job_id=job_id)
        
        stmt = select(Extraction).where(Extraction.id == job_id)
        result = await self.db.execute(stmt)
        extraction = result.scalar_one_or_none()
        
        if not extraction:
            logger.warning("extraction_job_not_found", job_id=job_id)
            raise NotFoundError(detail="Extraction job not found", error_code="DPT_004")
            
        return JobStatusResponse(
            job_id=extraction.id,
            status=extraction.status.value,
            document_type=extraction.document_type,
            confidence=extraction.confidence,
            model_version=extraction.model_version,
            created_at=extraction.created_at,
            updated_at=extraction.updated_at,
            completed_at=extraction.completed_at
        )

    async def get_extraction_result(self, job_id: int) -> ExtractionResultResponse:
        """Retrieve the structured JSON output from a completed extraction.

        Args:
            job_id: ID of the extraction job

        Returns:
            Structured JSON output and metadata

        Raises:
            NotFoundError: If job doesn't exist
        """
        logger.info("retrieving_extraction_result", job_id=job_id)
        
        stmt = select(Extraction).where(Extraction.id == job_id)
        result = await self.db.execute(stmt)
        extraction = result.scalar_one_or_none()
        
        if not extraction:
            logger.warning("extraction_job_not_found", job_id=job_id)
            raise NotFoundError(detail="Extraction job not found", error_code="DPT_004")
            
        return ExtractionResultResponse(
            job_id=extraction.id,
            extracted_json=extraction.extracted_json,
            confidence=extraction.confidence,
            model_version=extraction.model_version,
            created_at=extraction.created_at,
            completed_at=extraction.completed_at
        )

    async def update_job_result(self, job_id: int, extracted_data: Dict[str, Any], confidence: Decimal, model_version: str) -> None:
        """Internal method to update job with extraction results.

        Args:
            job_id: ID of the extraction job
            extracted_data: Structured data from Donut
            confidence: Confidence score of the extraction
            model_version: Version of the model used
        """
        logger.info("updating_job_result", job_id=job_id, confidence=float(confidence))
        
        stmt = select(Extraction).where(Extraction.id == job_id)
        result = await self.db.execute(stmt)
        extraction = result.scalar_one_or_none()
        
        if not extraction:
            logger.error("extraction_job_not_found_for_update", job_id=job_id)
            raise NotFoundError(detail="Extraction job not found", error_code="DPT_004")
            
        extraction.extracted_json = extracted_data
        extraction.confidence = confidence
        extraction.model_version = model_version
        extraction.status = ExtractionStatusEnum.COMPLETED
        extraction.completed_at = datetime.utcnow()
        
        await self.db.commit()