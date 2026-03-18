from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.dpt.schemas import DPTExtractResponse, DPTJobStatusResponse, DPTResultResponse
from mortgage_underwriting.modules.dpt.services import DPTService

router = APIRouter(prefix="/api/v1/dpt", tags=["Document Processing Transformer (DPT)"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/extract", response_model=DPTExtractResponse, status_code=status.HTTP_201_CREATED)
async def submit_extraction(
    application_id: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_session),
) -> DPTExtractResponse:
    """Submit a PDF document for asynchronous extraction using Donut models.
    
    Supports T4/T4A, NOA, Credit Reports, Bank Statements, and Purchase Agreements.
    Files are uploaded to S3 and queued for processing.
    """
    # Validate file size
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "detail": f"File size exceeds 10MB limit ({len(file_content)} bytes)",
                "error_code": "DPT_007"
            }
        )
    
    # Reset file pointer after reading
    await file.seek(0)
    
    # Validate MIME type
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": f"Invalid file format: {file.content_type}. Only application/pdf allowed",
                "error_code": "DPT_003"
            }
        )
    
    # Validate document_type
    allowed_types = ["t4", "noa", "credit", "bank", "purchase"]
    if document_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "detail": f"document_type must be one of: {', '.join(allowed_types)}",
                "error_code": "DPT_002"
            }
        )
    
    # TODO: Implement actual business logic:
    # 1. Upload file to S3
    # 2. Create Extraction record in DB
    # 3. Queue job for Donut processing
    # 4. Return job ID and initial status
    
    # Placeholder response - replace with real implementation
    return DPTExtractResponse(
        job_id=UUID('12345678-1234-5678-1234-567812345678'),
        status="pending",
        submitted_at="2023-01-01T00:00:00Z",
        estimated_completion_time="2023-01-01T00:05:00Z"
    )


@router.get("/jobs/{job_id}", response_model=DPTJobStatusResponse)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> DPTJobStatusResponse:
    """Poll the status of a document extraction job."""
    service = DPTService(db)
    try:
        return await service.get_job_status(job_id)
    except Exception as e:
        # Re-raise AppExceptions, convert others
        if hasattr(e, 'error_code'):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "detail": "Failed to retrieve job status",
                "error_code": "DPT_006"
            }
        )


@router.get("/results/{job_id}", response_model=DPTResultResponse)
async def get_extraction_result(
    job_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> DPTResultResponse:
    """Retrieve structured JSON output from a completed extraction."""
    service = DPTService(db)
    try:
        return await service.get_extraction_result(job_id)
    except Exception as e:
        # Re-raise AppExceptions, convert others
        if hasattr(e, 'error_code'):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "detail": "Failed to retrieve extraction result",
                "error_code": "DPT_008"
            }
        )