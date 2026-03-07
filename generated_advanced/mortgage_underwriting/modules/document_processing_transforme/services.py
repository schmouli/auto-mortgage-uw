from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid
from datetime import datetime
from uuid import UUID
from sqlalchemy import select
import structlog
from mortgage_underwriting.modules.dpt.models import Extraction
from mortgage_underwriting.modules.dpt.schemas import DPTExtractionRequest, DPTExtractionResponse, ExtractionResultResponse
from mortgage_underwriting.modules.dpt.exceptions import JobNotFoundError

default_model_version = "v1.2-dpt-extractor"
default_processing_time = 45
default_confidence_threshold = 0.85
logger = structlog.get_logger()

class DPTService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def submit_extraction(self, payload: DPTExtractionRequest) -> DPTExtractionResponse:
        """Submit a new document for extraction."""
        logger.info("submitting_document_for_extraction", 
                   application_id=payload.application_id, 
                   document_type=payload.document_type)
        
        # Create extraction record
        extraction = Extraction(
            application_id=payload.application_id,
            document_type=payload.document_type,
            s3_key=payload.s3_key or f"temp/{uuid.uuid4()}"
        )
        
        self.db.add(extraction)
        await self.db.commit()
        await self.db.refresh(extraction)
        
        return DPTExtractionResponse(
            job_id=uuid.uuid4(),
            status="pending",
            document_type=payload.document_type,
            created_at=extraction.created_at,
            estimated_processing_time_seconds=default_processing_time
        )

    async def get_extraction_status(self, job_id: UUID) -> Optional[DPTExtractionResponse]:
        """Get the status of an extraction job."""
        logger.info("checking_extraction_status", job_id=str(job_id))
        
        # FIXED: Query database using job_id instead of hardcoded ID
        stmt = select(Extraction).where(Extraction.id == job_id)  
        result = await self.db.execute(stmt)
        extraction = result.scalar_one_or_none()
        
        if not extraction:
            return None
            
        return DPTExtractionResponse(
            job_id=job_id,
            status=extraction.status,
            document_type=extraction.document_type,
            created_at=extraction.created_at,
            estimated_processing_time_seconds=default_processing_time
        )

    async def get_extraction_result(self, job_id: UUID) -> Optional[ExtractionResultResponse]:
        """Retrieve the structured JSON output from extraction."""
        logger.info("retrieving_extraction_result", job_id=str(job_id))
        
        # FIXED: Query database using job_id instead of hardcoded ID
        stmt = select(Extraction).where(Extraction.id == job_id)  
        result = await self.db.execute(stmt)
        extraction = result.scalar_one_or_none()
        
        if not extraction:
            return None
            
        return ExtractionResultResponse.model_validate(extraction)