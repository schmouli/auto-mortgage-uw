from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from .schemas import (
    ExtractionRequest,
    ExtractionResponse,
    JobStatusResponse,
    ExtractionResultResponse
)
from .services import DPTService
from ..database import get_db_session


router = APIRouter(prefix="/dpt", tags=["Document Processing Transformer"])


@router.post("/extract", response_model=ExtractionResponse, summary="Submit PDF for Extraction")
async def submit_pdf_for_extraction(
    request: ExtractionRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Submit a PDF document stored in S3 for extraction by the Donut model.

    The system will asynchronously process the document and make the results available later via polling.
    
    Example usage:
    ```json
    {
      "application_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "document_type": "t4506",
      "s3_key": "documents/t4_example.pdf"
    }
    ```
    """
    service = DPTService(db)
    try:
        job_id = await service.submit_extraction(request)
        return ExtractionResponse(
            job_id=job_id,
            application_id=request.application_id,
            document_type=request.document_type,
            status="pending"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/jobs/{job_id}", response_model=JobStatusResponse, summary="Poll Extraction Status")
async def poll_extraction_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Check the status of a previously submitted extraction job.

    Possible statuses:
    - pending: Job received but not yet started
    - processing: Currently being analyzed by Donut
    - completed: Successfully finished
    - failed: An error occurred during processing
    
    Example response:
    ```json
    {
      "job_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "application_id": "a1b2c3d4-e5f6-7890-g1h2-i3j4k5l6m7n8",
      "document_type": "t4506",
      "status": "completed",
      "started_at": "2023-01-01T10:00:00Z",
      "completed_at": "2023-01-01T10:05:00Z"
    }
    ```
    """
    service = DPTService(db)
    try:
        return await service.get_job_status(job_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/results/{job_id}", response_model=ExtractionResultResponse, summary="Get Extraction Results")
async def get_extraction_results(
    job_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieve the structured data extracted from a successfully processed document.
    
    Only available for jobs with 'completed' status.
    """
    service = DPTService(db)
    try:
        return await service.get_extraction_result(job_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/extractions", summary="List Extractions")
async def list_extractions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),  # FIXED: Added pagination parameters
    db: AsyncSession = Depends(get_db_session)
):
    """
    List all document extractions with pagination support.
    
    Query Parameters:
    - skip: Number of records to skip (default: 0)
    - limit: Number of records to return (default: 100, max: 100)
    """
    service = DPTService(db)
    try:
        return await service.list_extractions(skip=skip, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
```

```