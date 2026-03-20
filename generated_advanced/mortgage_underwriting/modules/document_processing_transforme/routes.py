from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.dpt.schemas import (
    ExtractionSubmitRequest,
    ExtractionSubmitResponse,
    ExtractionStatusResponse,
    ExtractionResultResponse,
)
from mortgage_underwriting.modules.dpt.services import DPTService
from mortgage_underwriting.modules.dpt.exceptions import (
    DPTInvalidInputError,
    DPTDocumentAlreadySubmittedError,
    DPTJobNotFoundError,
)

router = APIRouter(prefix="/api/v1/dpt", tags=["Document Processing Transformer"])


@router.post("/extract", response_model=ExtractionSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_document_for_extraction(
    payload: ExtractionSubmitRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExtractionSubmitResponse:
    """Submit a PDF document for asynchronous extraction."""
    try:
        service = DPTService(db)
        return await service.submit_extraction_job(payload)
    except DPTInvalidInputError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "DPT_002"}
        )
    except DPTDocumentAlreadySubmittedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": str(e), "error_code": "DPT_003"}
        )


@router.get("/jobs/{job_id}", response_model=ExtractionStatusResponse)
async def get_extraction_job_status(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExtractionStatusResponse:
    """Poll extraction job status."""
    try:
        service = DPTService(db)
        return await service.get_job_status(job_id)
    except DPTJobNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "DPT_004"}
        )


@router.get("/results/{job_id}", response_model=ExtractionResultResponse)
async def get_extraction_results(
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExtractionResultResponse:
    """Retrieve structured JSON output from completed extraction."""
    try:
        service = DPTService(db)
        return await service.get_extraction_result(job_id)
    except DPTJobNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "DPT_004"}
        )