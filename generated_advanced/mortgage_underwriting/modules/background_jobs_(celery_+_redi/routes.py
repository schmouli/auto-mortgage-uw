```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from . import schemas, services
from common.dependencies import get_current_user, get_db  # Hypothetical dependencies


router = APIRouter(prefix="/background-jobs", tags=["Background Jobs"])


@router.get("/", response_model=List[schemas.BackgroundJobResponse])
async def list_background_jobs(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Retrieve all background jobs.
    """
    try:
        result = await db.execute(services.select(services.BackgroundJob))
        jobs = result.scalars().all()
        return jobs
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/", response_model=schemas.BackgroundJobResponse, status_code=status.HTTP_201_CREATED)
async def create_background_job(
    job_in: schemas.BackgroundJobCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new background job.
    """
    try:
        new_job = services.BackgroundJob(**job_in.dict())
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
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update an existing background job by ID.
    """
    try:
        result = await db.execute(
            services.select(services.BackgroundJob).where(services.BackgroundJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        for key, value in job_update.dict(exclude_unset=True).items():
            setattr(job, key, value)

        await db.commit()
        await db.refresh(job)
        return job
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_background_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete a background job by ID.
    """
    try:
        result = await db.execute(
            services.select(services.BackgroundJob).where(services.BackgroundJob.id == job_id)
        )
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```