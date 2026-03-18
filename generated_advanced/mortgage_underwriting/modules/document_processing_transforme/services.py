from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from sqlalchemy import select
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.dpt.models import Extraction
from mortgage_underwriting.modules.dpt.schemas import DPTJobStatusResponse, DPTResultResponse

logger = structlog.get_logger()


class DPTService:
    """Business logic for Document Processing Transformer (Donut) service."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_job_status(self, job_id: UUID) -> DPTJobStatusResponse:
        """Retrieve the current status of an extraction job.
        
        Args:
            job_id: Unique identifier for the extraction job
            
        Returns:
            Job status information
            
        Raises:
            AppException: If job not found or database error occurs
        """
        logger.info("dpt_get_job_status", job_id=str(job_id))
        
        stmt = select(Extraction).where(Extraction.id == job_id)
        result = await self.db.execute(stmt)
        extraction: Optional[Extraction] = result.scalar_one_or_none()
        
        if not extraction:
            logger.warning("dpt_job_not_found", job_id=str(job_id))
            raise AppException(
                detail=f"Extraction job {job_id} not found",
                error_code="DPT_001"
            )
            
        return DPTJobStatusResponse.model_validate(extraction)

    async def get_extraction_result(self, job_id: UUID) -> DPTResultResponse:
        """Retrieve the structured output from a completed extraction.
        
        Args:
            job_id: Unique identifier for the extraction job
            
        Returns:
            Structured JSON result with confidence metrics
            
        Raises:
            AppException: If job not found, not completed, or database error
        """
        logger.info("dpt_get_extraction_result", job_id=str(job_id))
        
        stmt = select(Extraction).where(Extraction.id == job_id)
        result = await self.db.execute(stmt)
        extraction: Optional[Extraction] = result.scalar_one_or_none()
        
        if not extraction:
            logger.warning("dpt_job_not_found", job_id=str(job_id))
            raise AppException(
                detail=f"Extraction job {job_id} not found",
                error_code="DPT_001"
            )
            
        if extraction.status != "completed":
            logger.warning("dpt_job_not_completed", job_id=str(job_id), status=extraction.status)
            raise AppException(
                detail=f"Extraction job {job_id} is not completed (status: {extraction.status})",
                error_code="DPT_004"
            )
            
        if not extraction.extracted_json:
            logger.error("dpt_missing_result", job_id=str(job_id))
            raise AppException(
                detail=f"Extraction job {job_id} completed but has no result",
                error_code="DPT_005"
            )
            
        return DPTResultResponse.model_validate(extraction)