from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.dpt_service.schemas import ExtractRequest, ExtractResponse, JobStatusResponse, ExtractionResultResponse
from mortgage_underwriting.modules.dpt_service.services import DPTService

router = APIRouter(prefix="/api/v1/dpt", tags=["Document Processing Transformer"])


def get_dpt_service(db: AsyncSession = Depends(get_async_session)) -> DPTService:
    return DPTService(db)


@router.post("/extract", response_model=ExtractResponse, status_code=status.HTTP_201_CREATED)
async def submit_extraction(
    payload: ExtractRequest,
    service: Annotated[DPTService, Depends(get_dpt_service)],
) -> ExtractResponse:
    """Submit a PDF document for extraction using Donut transformer.
    
    Raises:
        HTTPException: 400 if validation fails
        HTTPException: 404 if application not found
    """
    try:
        return await service.submit_extraction_job(payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "DPT_001"}
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to submit extraction job", "error_code": "DPT_003"}
        )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: int,
    service: Annotated[DPTService, Depends(get_dpt_service)],
) -> JobStatusResponse:
    """Poll the status of an extraction job."""
    try:
        return await service.get_job_status(job_id)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to retrieve job status", "error_code": "DPT_005"}
        )


@router.get("/results/{job_id}", response_model=ExtractionResultResponse)
async def get_extraction_result(
    job_id: int,
    service: Annotated[DPTService, Depends(get_dpt_service)],
) -> ExtractionResultResponse:
    """Retrieve structured JSON output from a completed extraction."""
    try:
        return await service.get_extraction_result(job_id)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to retrieve extraction result", "error_code": "DPT_007"}
        )