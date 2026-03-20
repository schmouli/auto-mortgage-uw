from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.background_jobs.schemas import JobCreate, JobUpdate, JobResponse
from mortgage_underwriting.modules.background_jobs.services import BackgroundJobService
from mortgage_underwriting.modules.background_jobs.exceptions import (
    JobNotFoundError,
    JobCreationError,
    JobUpdateError,
    JobDeletionError,
    JobTriggerError
)

router = APIRouter(prefix="/api/v1/background-jobs", tags=["Background Jobs"])


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_background_job(
    payload: JobCreate,
    db: AsyncSession = Depends(get_async_session),
) -> JobResponse:
    """Create a new background job configuration."""
    service = BackgroundJobService(db)
    try:
        return await service.create_job(payload)
    except JobCreationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{job_id}", response_model=JobResponse)
async def get_background_job(
    job_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> JobResponse:
    """Get a specific background job by ID."""
    service = BackgroundJobService(db)
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/", response_model=List[JobResponse])
async def list_background_jobs(
    limit: int = Query(100, le=100, gt=0),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
) -> List[JobResponse]:
    """List background jobs with pagination."""
    service = BackgroundJobService(db)
    return await service.list_jobs(limit=limit, offset=offset)


@router.put("/{job_id}", response_model=JobResponse)
async def update_background_job(
    job_id: int,
    payload: JobUpdate,
    db: AsyncSession = Depends(get_async_session),
) -> JobResponse:
    """Update a background job configuration."""
    service = BackgroundJobService(db)
    try:
        job = await service.update_job(job_id, payload)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return job
    except JobUpdateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_background_job(
    job_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> None:
    """Delete a background job configuration."""
    service = BackgroundJobService(db)
    try:
        deleted = await service.delete_job(job_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    except JobDeletionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{job_id}/trigger", response_model=JobResponse)
async def trigger_background_job(
    job_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> JobResponse:
    """Manually trigger a background job to run immediately."""
    service = BackgroundJobService(db)
    try:
        job = await service.trigger_job(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return job
    except JobTriggerError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))