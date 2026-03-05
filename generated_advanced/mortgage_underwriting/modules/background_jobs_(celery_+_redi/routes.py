from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from . import schemas, services
from .models import BackgroundJob
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.common.security import get_current_user


router = APIRouter(prefix="/api/v1/background-jobs", tags=["Background Jobs"])


@router.get("/", response_model=List[schemas.BackgroundJobResponse])
async def list_background_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=100, ge=1),
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Retrieve all background jobs with pagination.
    """
    try:
        job_service = services.BackgroundJobService(db)
        jobs = await job_service.list_jobs(skip=skip, limit=limit)
        return jobs
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/", response_model=schemas.BackgroundJobResponse, status_code=status.HTTP_201_CREATED)
async def create_background_job(
    job_in: schemas.BackgroundJobCreate,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Create a new background job.
    """
    try:
        new_job = BackgroundJob(**job_in.model_dump())
        db.add(new_job)
        await db.commit()
        await db.refresh(new_job)
        return new_job
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{job_id}", response_model=schemas.BackgroundJobResponse)
async def update_background_job(
    job_id: int,
    job_update: schemas.BackgroundJobUpdate,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Update an existing background job.
    """
    try:
        result = await db.execute(select(BackgroundJob).where(BackgroundJob.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
            
        for field, value in job_update.model_dump(exclude_unset=True).items():
            setattr(job, field, value)
            
        await db.commit()
        await db.refresh(job)
        return job
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{job_id}", response_model=schemas.BackgroundJobResponse)
async def get_background_job(
    job_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Get a specific background job by ID.
    """
    try:
        result = await db.execute(select(BackgroundJob).where(BackgroundJob.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
            
        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_background_job(
    job_id: int,
    db: AsyncSession = Depends(get_async_session),
    current_user = Depends(get_current_user)
):
    """
    Delete a background job.
    """
    try:
        result = await db.execute(select(BackgroundJob).where(BackgroundJob.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
            
        await db.delete(job)
        await db.commit()
        return
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
```

```