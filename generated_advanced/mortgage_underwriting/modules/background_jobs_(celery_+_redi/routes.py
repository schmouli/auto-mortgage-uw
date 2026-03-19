from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.jobs.schemas import (
    JobExecutionRequest,
    JobExecutionResponse,
    ScheduledJobSchema,
    ScheduledJobUpdate,
    JobExecutionLogSchema,
    JobExecutionFilterQuery
)
from mortgage_underwriting.modules.jobs.services import JobService

router = APIRouter(prefix="/api/v1/jobs", tags=["Background Jobs"])


def get_job_service(db: AsyncSession = Depends(get_async_session)) -> JobService:
    return JobService(db)


@router.post("/{job_name}/run", response_model=JobExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_job(
    job_name: str,
    payload: Optional[JobExecutionRequest] = None,
    service: JobService = Depends(get_job_service)
) -> JobExecutionResponse:
    """Trigger immediate execution of a background job."""
    try:
        return await service.trigger_job(job_name, payload)
    except (NotFoundError, AppException) as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "JOB_003"})


@router.get("/{job_name}/status", response_model=ScheduledJobSchema)
async def get_job_status(
    job_name: str,
    service: JobService = Depends(get_job_service)
) -> ScheduledJobSchema:
    """Get the current status of a scheduled job."""
    try:
        return await service.get_scheduled_job(job_name)
    except NotFoundError as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": str(e), "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "JOB_003"})
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "JOB_003"})


@router.patch("/{job_name}", response_model=ScheduledJobSchema)
async def update_job(
    job_name: str,
    payload: ScheduledJobUpdate,
    service: JobService = Depends(get_job_service)
) -> ScheduledJobSchema:
    """Enable or disable a scheduled job."""
    try:
        return await service.update_job_status(job_name, payload)
    except NotFoundError as e:
        if hasattr(e, 'error_code'):
            if e.error_code == "JOB_001":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": str(e), "error_code": e.error_code})
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"detail": str(e), "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "JOB_003"})
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "JOB_003"})


@router.get("/executions", response_model=List[JobExecutionLogSchema])
async def list_job_executions(
    filters: JobExecutionFilterQuery = Depends(),
    service: JobService = Depends(get_job_service)
) -> List[JobExecutionLogSchema]:
    """List job executions with filtering and pagination."""
    try:
        return await service.list_job_executions(filters)
    except AppException as e:
        # FIXED: Proper error handling for validation errors
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": e.error_code})
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "JOB_003"})


@router.get("/scheduled", response_model=List[ScheduledJobSchema])
async def list_scheduled_jobs(
    service: JobService = Depends(get_job_service)
) -> List[ScheduledJobSchema]:
    """List all scheduled jobs."""
    try:
        return await service.list_scheduled_jobs()
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": "Internal server error", "error_code": "JOB_003"})