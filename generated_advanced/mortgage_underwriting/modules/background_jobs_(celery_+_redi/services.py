from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.background_jobs.models import BackgroundJob
from mortgage_underwriting.modules.background_jobs.schemas import JobCreate, JobUpdate, JobResponse
from mortgage_underwriting.modules.background_jobs.exceptions import (
    JobCreationError,
    JobNotFoundError,
    JobUpdateError,
    JobDeletionError,
    JobTriggerError
)

logger = structlog.get_logger()


class BackgroundJobService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_job(self, payload: JobCreate) -> JobResponse:
        """Create a new background job."""
        logger.info("creating_background_job", name=payload.name)
        try:
            job = BackgroundJob(**payload.model_dump())
            self.db.add(job)
            await self.db.commit()
            await self.db.refresh(job)
            return JobResponse.model_validate(job)
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error("failed_to_create_job", error=str(e))
            raise JobCreationError(f"Failed to create job: {str(e)}") from e

    async def get_job(self, job_id: int) -> Optional[JobResponse]:
        """Get a specific background job by ID."""
        logger.info("fetching_background_job", job_id=job_id)
        stmt = select(BackgroundJob).where(BackgroundJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()
        return JobResponse.model_validate(job) if job else None

    async def list_jobs(self, limit: int = 100, offset: int = 0) -> List[JobResponse]:
        """List background jobs with pagination."""
        logger.info("listing_background_jobs", limit=limit, offset=offset)
        stmt = select(BackgroundJob).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        jobs = result.scalars().all()
        return [JobResponse.model_validate(job) for job in jobs]

    async def update_job(self, job_id: int, payload: JobUpdate) -> Optional[JobResponse]:
        """Update a background job configuration."""
        logger.info("updating_background_job", job_id=job_id)
        try:
            stmt = update(BackgroundJob).where(BackgroundJob.id == job_id).values(**payload.model_dump(exclude_unset=True))
            await self.db.execute(stmt)
            await self.db.commit()
            
            updated_stmt = select(BackgroundJob).where(BackgroundJob.id == job_id)
            result = await self.db.execute(updated_stmt)
            job = result.scalar_one_or_none()
            return JobResponse.model_validate(job) if job else None
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error("failed_to_update_job", job_id=job_id, error=str(e))
            raise JobUpdateError(f"Failed to update job: {str(e)}") from e

    async def delete_job(self, job_id: int) -> bool:
        """Delete a background job configuration."""
        logger.info("deleting_background_job", job_id=job_id)
        try:
            stmt = select(BackgroundJob).where(BackgroundJob.id == job_id)
            result = await self.db.execute(stmt)
            job = result.scalar_one_or_none()
            if job:
                await self.db.delete(job)
                await self.db.commit()
                return True
            return False
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error("failed_to_delete_job", job_id=job_id, error=str(e))
            raise JobDeletionError(f"Failed to delete job: {str(e)}") from e

    async def trigger_job(self, job_id: int) -> Optional[JobResponse]:
        """Manually trigger a background job to run immediately."""
        logger.info("triggering_background_job", job_id=job_id)
        # In a real implementation, this would enqueue the task
        # For now we'll just update the status to 'running' and schedule it
        try:
            stmt = update(BackgroundJob).where(BackgroundJob.id == job_id).values(
                status="running",
                last_run_at=datetime.utcnow()
            )
            await self.db.execute(stmt)
            await self.db.commit()
            
            updated_stmt = select(BackgroundJob).where(BackgroundJob.id == job_id)
            result = await self.db.execute(updated_stmt)
            job = result.scalar_one_or_none()
            return JobResponse.model_validate(job) if job else None
        except SQLAlchemyError as e:
            await self.db.rollback()
            logger.error("failed_to_trigger_job", job_id=job_id, error=str(e))
            raise JobTriggerError(f"Failed to trigger job: {str(e)}") from e