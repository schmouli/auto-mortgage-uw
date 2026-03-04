```python
import asyncio
import logging
from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from .models import Extraction
from .schemas import ExtractionRequest, JobStatusResponse, ExtractionResultResponse
from .exceptions import (
    DPTServiceException,
    DocumentProcessingFailedException,
    ExtractionNotFoundException
)


logger = logging.getLogger(__name__)


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
            extraction = Extraction(
                application_id=request.application_id,
                document_type=request.document_type,
                s3_key=request.s3_key,
                extracted_json={},  # Placeholder until processing completes
                model_version="donut-v1.0"  # Static versioning example
            )
            
            self.db.add(extraction)
            await self.db.commit()
            await self.db.refresh(extraction)

            # Schedule background task for processing
            asyncio.create_task(self._process_document_async(extraction.id))

            logger.info(f"Submitted extraction job {extraction.id} for app {request.application_id}")
            return extraction.id

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to submit extraction request: {str(e)}")
            raise DPTServiceException("Failed to submit extraction request") from e

    async def get_job_status(self, job_id: UUID) -> JobStatusResponse:
        """
        Retrieve current status of an extraction job.

        Args:
            job_id: Unique identifier for the job.

        Returns:
            JobStatusResponse indicating job state and timestamps.
        """
        stmt = select(Extraction).where(Extraction.id == job_id)
        result = await self.db.execute(stmt)
        extraction = result.scalar_one_or_none()

        if not extraction:
            raise ExtractionNotFoundException(f"No extraction found with job_id {job_id}")

        # For simplicity, assume all jobs complete immediately after submission
        status_map = {
            bool(extraction.extracted_json): "completed",
            True: "completed",
            False: "processing"
        }

        status = status_map.get(bool(extraction.extracted_json), "pending")

        return JobStatusResponse(
            job_id=extraction.id,
            application_id=extraction.application_id,
            document_type=extraction.document_type,
            status=status,
            started_at=extraction.created_at,
            completed_at=getattr(extraction, 'updated_at', None)
        )

    async def get_extraction_result(self, job_id: UUID) -> ExtractionResultResponse:
        """
        Retrieve results of a completed extraction job.

        Args:
            job_id: Unique identifier for the job.

        Returns:
            ExtractionResultResponse containing structured JSON output.
        """
        stmt = select(Extraction).where(Extraction.id == job_id)
        result = await self.db.execute(stmt)
        extraction = result.scalar_one_or_none()

        if not extraction:
            raise ExtractionNotFoundException(f"No extraction found with job_id {job_id}")

        if not extraction.extracted_json:
            raise DocumentProcessingFailedException("Document has not been processed yet")

        return ExtractionResultResponse(
            job_id=extraction.id,
            application_id=extraction.application_id,
            document_type=extraction.document_type,
            extracted_json=extraction.extracted_json,
            confidence=extraction.confidence,
            model_version=extraction.model_version
        )

    async def _process_document_async(self, job_id: UUID):
        """
        Background worker to simulate document processing using Donut model.

        This would typically interface with the Donut inference engine or API.

        Args:
            job_id: Identifier of the extraction job to process.
        """
        try:
            # Simulate delay for asynchronous operation
            await asyncio.sleep(5)

            # Mock extraction based on document type
            mock_results = self._mock_donut_inference(job_id)

            # Update database with results
            stmt = (
                update(Extraction)
                .where(Extraction.id == job_id)
                .values(
                    extracted_json=mock_results["data"],
                    confidence=mock_results["confidence"]
                )
            )
            await self.db.execute(stmt)
            await self.db.commit()

            logger.info(f"Completed processing for job {job_id}")

        except Exception as e:
            logger.error(f"Error during document processing for job {job_id}: {str(e)}")
            raise DocumentProcessingFailedException(f"Processing failed for job {job_id}") from e

    def _mock_donut_inference(self, job_id: UUID) -> Dict[str, Any]:
        """
        Mock implementation simulating Donut inference outputs per document type.

        Args:
            job_id: Identifier of the extraction job.

        Returns:
            Dictionary with mocked extracted data and confidence score.
        """
        # In real-world scenario, this would call the Donut model endpoint
        sample_data = {
            "t4506": {"employer": "ABC Corp", "income_ytd": 75000},
            "noa": {"line_15000": 85000, "line_23600": 12000, "tax_year": 2023},
            "credit": {"score": 720, "inquiries": 3, "collections": []},
            "bank": {"balance": 15000, "transactions": [{"date": "2023-01-01", "amount": 2000}]},
            "purchase": {"price": 650000, "closing_date": "2024-06-30", "address": "123 Main St"}
        }

        # Fetch document type from DB
        stmt = select(Extraction.document_type).where(Extraction.id == job_id)
        result = self.db.execute(stmt)
        doc_type = result.scalar_one()

        return {
            "data": sample_data.get(doc_type, {}),
            "confidence": 0.95
        }
```