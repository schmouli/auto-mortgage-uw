from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.dpt.schemas import (
    ExtractionSubmitRequest,
    ExtractionSubmitResponse,
    ExtractionStatusResponse,
    ExtractionResultResponse
)
from mortgage_underwriting.modules.dpt.services import DPTService
from mortgage_underwriting.modules.dpt.exceptions import DPTApplicationNotFoundError, DPTInvalidDocumentTypeError

router = APIRouter(prefix="/api/v1/dpt", tags=["Document Processing Transformer"])


def get_dpt_service(
    db: Annotated[
        get_async_session, 
        Depends(get_async_session)
    ]
) -> DPTService:
    return DPTService(db)


@router.post("/extract", response_model=ExtractionSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_extraction(
    payload: ExtractionSubmitRequest,
    service: Annotated[DPTService, Depends(get_dpt_service)]
) -> ExtractionSubmitResponse:
    """Submit PDF for extraction."""
    try:
        return await service.submit_extraction_job(payload)
    except DPTApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {e.application_id} not found",
            headers={"X-Error-Code": "DPT_001"}
        )
    except DPTInvalidDocumentTypeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
            headers={"X-Error-Code": "DPT_002"}
        )


@router.get("/jobs/{job_id}", response_model=ExtractionStatusResponse)
async def get_job_status(
    job_id: UUID,
    service: Annotated[DPTService, Depends(get_dpt_service)]
) -> ExtractionStatusResponse:
    """Poll extraction status."""
    try:
        return await service.get_job_status(job_id)
    except DPTApplicationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
            headers={"X-Error-Code": "DPT_001"}
        )


@router.get("/results/{job_id}", response_model=ExtractionResultResponse)
async def get_extraction_result(
    job_id: UUID,
    service: Annotated[DPTService, Depends(get_dpt_service)]
) -> ExtractionResultResponse:
    """Retrieve structured JSON output."""
    try:
        return await service.get_extraction_result(job_id)
    except DPTApplicationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
            headers={"X-Error-Code": "DPT_001"}
        )