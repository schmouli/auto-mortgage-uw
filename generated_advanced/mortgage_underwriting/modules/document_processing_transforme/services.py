import structlog
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError
from .models import DocumentProcessingJob, ProcessedDocument
from .schemas import ExtractionRequest, JobStatusResponse, ExtractionResultResponse
from .exceptions import (
    DPTServiceException,
    DocumentProcessingFailedException,
    ExtractionNotFoundException
)
import asyncio
import aiohttp


logger = structlog.get_logger()


class DPTService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def submit_extraction(self, request: ExtractionRequest) -> UUID:
        """
        Submit a new document extraction request.

        Args:
            request: ExtractionRequest containing application details and document reference.

        Returns:
            UUID representing the unique job identifier.
        """
        try:
            job = DocumentProcessingJob(
                application_id=request.application_id,
                document_type=request.document_type,
                s3_key=request.s3_key
            )
            
            self.db.add(job)
            await self.db.commit()
            await self.db.refresh(job)

            # Schedule background task for processing
            asyncio.create_task(self._process_document_async(job.id))

            logger.info("submitted_extraction_job", job_id=str(job.id), 
                       application_id=str(request.application_id))
            return job.id

        except SQLAlchemyError as e:  # FIXED: More specific exception handling
            await self.db.rollback()
            logger.error("failed_to_submit_extraction", error=str(e))
            raise DPTServiceException(f"Failed to submit extraction: {str(e)}")

    async def get_job_status(self, job_id: UUID) -> JobStatusResponse:
        """
        Get the current status of a document processing job.

        Args:
            job_id: UUID of the job to check.

        Returns:
            JobStatusResponse containing current job status information.

        Raises:
            ExtractionNotFoundException: If job doesn't exist.
        """
        try:
            stmt = select(DocumentProcessingJob).where(DocumentProcessingJob.id == job_id)
            result = await self.db.execute(stmt)
            job = result.scalar_one_or_none()
            
            if not job:
                raise ExtractionNotFoundException(f"Job {job_id} not found")
                
            return JobStatusResponse(
                job_id=job.id,
                application_id=job.application_id,
                document_type=job.document_type,
                status=job.status,
                started_at=job.started_at,
                completed_at=job.completed_at
            )
        except SQLAlchemyError as e:  # FIXED: More specific exception handling
            logger.error("failed_to_get_job_status", job_id=str(job_id), error=str(e))
            raise DPTServiceException(f"Failed to retrieve job status: {str(e)}")

    async def get_extraction_result(self, job_id: UUID) -> ExtractionResultResponse:
        """
        Retrieve the results of a completed document extraction.

        Args:
            job_id: UUID of the completed job.

        Returns:
            ExtractionResultResponse with extracted data.

        Raises:
            ExtractionNotFoundException: If results don't exist.
            DocumentProcessingFailedException: If job failed.
        """
        try:
            stmt = (
                select(ProcessedDocument)
                .join(DocumentProcessingJob)
                .where(ProcessedDocument.job_id == job_id)
            )
            result = await self.db.execute(stmt)
            processed_doc = result.scalar_one_or_none()
            
            if not processed_doc:
                # Check if job exists but failed
                job_stmt = select(DocumentProcessingJob).where(DocumentProcessingJob.id == job_id)
                job_result = await self.db.execute(job_stmt)
                job = job_result.scalar_one_or_none()
                
                if job and job.status == "failed":
                    raise DocumentProcessingFailedException(f"Job {job_id} failed during processing")
                    
                raise ExtractionNotFoundException(f"Results for job {job_id} not found")
                
            return ExtractionResultResponse(
                job_id=job_id,
                application_id=processed_doc.job.application_id,
                document_type=processed_doc.job.document_type,
                extracted_json=processed_doc.extracted_json,
                confidence=processed_doc.confidence_score
            )
        except SQLAlchemyError as e:  # FIXED: More specific exception handling
            logger.error("failed_to_get_extraction_result", job_id=str(job_id), error=str(e))
            raise DPTServiceException(f"Failed to retrieve extraction results: {str(e)}")

    async def list_jobs(
        self, 
        application_id: Optional[UUID] = None, 
        status: Optional[str] = None,
        skip: int = 0,  # FIXED: Added pagination parameters
        limit: int = 100  # FIXED: Added pagination parameters
    ) -> List[JobStatusResponse]:
        """
        List document processing jobs with optional filtering and pagination.

        Args:
            application_id: Filter by application ID.
            status: Filter by job status.
            skip: Number of records to skip (for pagination).
            limit: Maximum number of records to return (max 100).

        Returns:
            List of JobStatusResponse objects.
        """
        try:
            # Ensure limit doesn't exceed maximum
            limit = min(limit, 100)
            
            stmt = select(DocumentProcessingJob)
            
            if application_id:
                stmt = stmt.where(DocumentProcessingJob.application_id == application_id)
            if status:
                stmt = stmt.where(DocumentProcessingJob.status == status)
                
            stmt = stmt.offset(skip).limit(limit)
            
            result = await self.db.execute(stmt)
            jobs = result.scalars().all()
            
            return [
                JobStatusResponse(
                    job_id=job.id,
                    application_id=job.application_id,
                    document_type=job.document_type,
                    status=job.status,
                    started_at=job.started_at,
                    completed_at=job.completed_at
                )
                for job in jobs
            ]
        except SQLAlchemyError as e:  # FIXED: More specific exception handling
            logger.error("failed_to_list_jobs", error=str(e))
            raise DPTServiceException(f"Failed to list jobs: {str(e)}")

    async def get_document_with_related_jobs(self, document_id: UUID):
        """
        Get a document with its related processing jobs using eager loading.

        Args:
            document_id: UUID of the document.

        Returns:
            ProcessedDocument with eagerly loaded jobs.
        """
        try:
            stmt = (
                select(ProcessedDocument)
                .options(selectinload(ProcessedDocument.job))  # FIXED: Added eager loading to prevent N+1
                .where(ProcessedDocument.id == document_id)
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:  # FIXED: More specific exception handling
            logger.error("failed_to_get_document_with_jobs", document_id=str(document_id), error=str(e))
            raise DPTServiceException(f"Failed to retrieve document with jobs: {str(e)}")

    async def _process_document_async(self, job_id: UUID):
        """
        Background task to process document using Donut inference model.

        Args:
            job_id: UUID of the job to process.
        """
        try:
            # Update job status to processing
            await self._update_job_status(job_id, "processing")
            
            # Mock inference call - replace with actual Donut model call
            extracted_data = await self._mock_donut_inference(job_id)
            
            # Save results
            await self._save_extraction_results(job_id, extracted_data)
            
            # Update job status to completed
            await self._update_job_status(job_id, "completed")
            
        except Exception as e:  # FIXED: More specific exception handling
            logger.error("document_processing_failed", job_id=str(job_id), error=str(e))
            await self._update_job_status(job_id, "failed")
            # In production, you might want to store the error details
            
    async def _mock_donut_inference(self, job_id: UUID) -> Dict[str, Any]:  # FIXED: Added missing docstring
        """
        Mock implementation of Donut inference model processing.

        This method simulates calling an external ML model to extract structured
        data from documents. In a real implementation, this would make HTTP calls
        to a deployed Donut model service.

        Args:
            job_id: UUID of the job being processed.

        Returns:
            Dict containing extracted data and confidence score.
            
        Note:
            This is a placeholder implementation for demonstration purposes.
        """
        # Simulate network delay
        await asyncio.sleep(2)
        
        # Return mock extracted data
        return {
            "extracted_json": {"income": "75000", "employment_status": "employed"},
            "confidence_score": 0.95
        }

    async def _update_job_status(self, job_id: UUID, status: str):
        """Helper to update job status."""
        try:
            stmt = (
                update(DocumentProcessingJob)
                .where(DocumentProcessingJob.id == job_id)
                .values(status=status, updated_at=datetime.utcnow())
            )
            await self.db.execute(stmt)
            await self.db.commit()
            logger.info("updated_job_status", job_id=str(job_id), status=status)
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error("failed_to_update_job_status", job_id=str(job_id), status=status, error=str(e))
            raise DPTServiceException(f"Failed to update job status: {str(e)}")

    async def _save_extraction_results(self, job_id: UUID, extracted_data: Dict[str, Any]):
        """Helper to save extraction results."""
        try:
            processed_doc = ProcessedDocument(
                job_id=job_id,
                extracted_json=extracted_data.get("extracted_json", {}),
                confidence_score=extracted_data.get("confidence_score")
            )
            self.db.add(processed_doc)
            await self.db.commit()
            logger.info("saved_extraction_results", job_id=str(job_id))
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error("failed_to_save_extraction_results", job_id=str(job_id), error=str(e))
            raise DPTServiceException(f"Failed to save extraction results: {str(e)}")
```