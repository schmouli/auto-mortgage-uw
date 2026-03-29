from typing import Annotated
import structlog

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.background_jobs.schemas import JobTriggerRequest, JobTriggerResponse, JobStatusResponse
from mortgage_underwriting.modules.background_jobs.services import BackgroundJobService

router = APIRouter(prefix="/api/v1/jobs", tags=["Background Jobs"])
logger = structlog.get_logger()


@router.post("/{job_name}/trigger", response_model=JobTriggerResponse, status_code=status.HTTP_200_OK)
async def trigger_background_job(
    job_name: str,
    payload: JobTriggerRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> JobTriggerResponse:
    """Manually trigger a background job (admin-only)."""
    service = BackgroundJobService(db)
    try:
        return await service.trigger_job(job_name, payload)
    except AppException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": e.error_code})
    except Exception:
        logger.exception("Unexpected error triggering job")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"})


@router.get("/{job_name}/status", response_model=JobStatusResponse)
async def get_background_job_status(
    job_name: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> JobStatusResponse:
    """Retrieve last execution status and history."""
    service = BackgroundJobService(db)
    try:
        return await service.get_job_status(job_name)
    except AppException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": str(e), "error_code": e.error_code})
    except Exception:
        logger.exception("Unexpected error getting job status")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"})