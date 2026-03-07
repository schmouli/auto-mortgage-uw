from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.dpt.schemas import DPTExtractionRequest, DPTExtractionResponse, ExtractionResultResponse
from mortgage_underwriting.modules.dpt.services import DPTService
from mortgage_underwriting.modules.dpt.exceptions import DPTException
router = APIRouter(prefix="/api/v1/dpt", tags=["Document Processing Transformer"])

@router.post("/extract", response_model=DPTExtractionResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_extraction(
    application_id: str = Form(...),
    document_type: str = Form(...),
    s3_key: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_async_session),
) -> DPTExtractionResponse:
    """Submit a PDF document for asynchronous extraction."""
    try:
        # FIXED: Convert application_id to int instead of UUID
        payload = DPTExtractionRequest(
            application_id=int(application_id),
            document_type=document_type,
            s3_key=s3_key
        )
        service = DPTService(db)
        return await service.submit_extraction(payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "INVALID_APPLICATION_ID"}
        )

@router.get("/jobs/{job_id}", response_model=DPTExtractionResponse)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> DPTExtractionResponse:
    """Poll extraction status."""
    service = DPTService(db)
    result = await service.get_extraction_status(job_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Job not found", "error_code": "JOB_NOT_FOUND"}
        )
    return result

@router.get("/results/{job_id}", response_model=ExtractionResultResponse)
async def get_extraction_result(
    job_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> ExtractionResultResponse:
    """Retrieve structured JSON output."""
    service = DPTService(db)
    result = await service.get_extraction_result(job_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Result not found", "error_code": "RESULT_NOT_FOUND"}
        )
    return result