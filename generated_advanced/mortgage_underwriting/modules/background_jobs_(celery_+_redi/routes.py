from typing import Optional

from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.scheduled_jobs.schemas import JobExecutionListResponse, JobExecutionDetail
from mortgage_underwriting.modules.scheduled_jobs.services import ScheduledJobService

router = APIRouter(prefix="/api/v1/admin/jobs", tags=["Scheduled Jobs"])


@router.get("/", response_model=JobExecutionListResponse)
async def list_job_executions(
    task_name: Optional[str] = Query(None, description="Filter by task name"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, le=100, description="Max results to return"),
    offset: int = Query(0, description="Pagination offset"),
    db: AsyncSession = Depends(get_async_session),
) -> JobExecutionListResponse:  # FIXED: Added return type hint
    """List recent job executions with filtering and pagination."""
    service = ScheduledJobService(db)
    return await service.list_executions(task_name=task_name, status=status, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobExecutionDetail)
async def get_job_execution_detail(
    job_id: str = Path(..., description="Unique job execution identifier"),
    db: AsyncSession = Depends(get_async_session),
) -> JobExecutionDetail:  # FIXED: Added return type hint
    """Get detailed information about a specific job execution."""
    service = ScheduledJobService(db)
    return await service.get_execution_detail(job_id)