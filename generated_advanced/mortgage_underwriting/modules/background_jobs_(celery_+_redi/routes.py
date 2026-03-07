from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.background_jobs.schemas import (
    JobTriggerRequest,
    JobTriggerResponse,
    JobStatusResponse,
    ScheduledJobListResponse,
    ScheduledJobResponse
)
from mortgage_underwriting.modules.background_jobs.services import BackgroundJobsService
from mortgage_underwriting.modules.background_jobs.exceptions import JobNotFoundError, InvalidTaskNameError

router = APIRouter(prefix="/api/v1/jobs", tags=["Background Jobs"])

# In a real implementation, you would have proper authentication/authorization
# For this example, we'll simulate getting user ID
async def get_current_user_id() -> int:
    # This is a placeholder - in reality this would extract user from token
    return 1

@router.post("/trigger/{task_name}", response_model=JobTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_job(
    task_name: str,
    payload: JobTriggerRequest,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    user_id: Annotated[int, Depends(get_current_user_id)]
) -> JobTriggerResponse:
    """Trigger a background job manually.
    
    Requires admin privileges (scope: jobs:manage).
    """
    try:
        # Update the task_name in payload to match path parameter
        payload.task_name = task_name
        service = BackgroundJobsService(db)
        return await service.trigger_job(payload, user_id)
    except InvalidTaskNameError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": str(e),
                "error_code": "JOBS_001"
            }
        )

@router.get("/status/{task_id}", response_model=JobStatusResponse)
async def get_job_status(
    task_id: str,
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> JobStatusResponse:
    """Get the status of a specific job execution.
    
    Requires admin privileges.
    """
    try:
        service = BackgroundJobsService(db)
        return await service.get_job_status(task_id)
    except JobNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": str(e),
                "error_code": "JOBS_002"
            }
        )

@router.get("/schedule", response_model=ScheduledJobListResponse)
async def get_scheduled_jobs(
    db: Annotated[AsyncSession, Depends(get_async_session)]
) -> ScheduledJobListResponse:
    """Get all configured scheduled jobs.
    
    Requires admin privileges.
    """
    service = BackgroundJobsService(db)
    return await service.get_scheduled_jobs()

@router.post("/schedule/{task_name}/enable", response_model=ScheduledJobResponse)
async def enable_scheduled_job(
    task_name: str,
    db: Annotated[AsyncSession, Depends(get_async_session)],
    user_id: Annotated[int, Depends(get_current_user_id)]
) -> ScheduledJobResponse:
    """Enable a scheduled job.
    
    Requires admin privileges.
    """
    try:
        service = BackgroundJobsService(db)
        return await service.enable_scheduled_job(task_name)
    except JobNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": str(e),
                "error_code": "JOBS_002"
            }
        )