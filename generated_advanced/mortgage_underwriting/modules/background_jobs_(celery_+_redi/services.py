from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional, Dict, Any
import uuid
import structlog

from mortgage_underwriting.common.exceptions import AppException, NotFoundError
from mortgage_underwriting.modules.jobs.models import ScheduledJob, JobExecutionLog
from mortgage_underwriting.modules.jobs.schemas import (
    ScheduledJobCreate,
    ScheduledJobUpdate,
    ScheduledJobSchema,
    JobExecutionRequest,
    JobExecutionResponse,
    JobExecutionLogSchema,
    JobExecutionFilterQuery
)

logger = structlog.get_logger()


class JobService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def trigger_job(self, job_name: str, payload: Optional[JobExecutionRequest] = None) -> JobExecutionResponse:
        """Trigger immediate execution of a background job.
        
        Args:
            job_name: Name of the job to execute
            payload: Optional parameters for the job execution
            
        Returns:
            Job execution response with execution ID
            
        Raises:
            NotFoundError: If job doesn't exist
            AppException: If job is disabled
        """
        # FIXED: Added input validation
        if not job_name or not job_name.strip():
            raise AppException("Job name cannot be empty", error_code="JOB_004")
            
        logger.info("job_trigger_requested", job_name=job_name)
        
        stmt = select(ScheduledJob).where(ScheduledJob.name == job_name)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            logger.warning("job_not_found", job_name=job_name)
            raise NotFoundError(f"Job '{job_name}' not found", error_code="JOB_001")
            
        if not job.enabled:
            logger.warning("job_disabled", job_name=job_name)
            raise AppException(f"Job '{job_name}' is disabled", error_code="JOB_002")
            
        execution_id = str(uuid.uuid4())
        
        # Log the execution start
        execution_log = JobExecutionLog(
            job_name=job_name,
            execution_id=execution_id,
            status="queued",
            params=payload.params if payload else None,
            started_at=datetime.utcnow()
        )
        
        self.db.add(execution_log)
        await self.db.commit()
        await self.db.refresh(execution_log)
        
        logger.info("job_execution_queued", job_name=job_name, execution_id=execution_id)
        
        return JobExecutionResponse(
            execution_id=execution_id,
            job_name=job_name,
            status="queued",
            started_at=execution_log.started_at
        )

    async def get_scheduled_job(self, job_name: str) -> ScheduledJobSchema:
        """Get details of a scheduled job.
        
        Args:
            job_name: Name of the job
            
        Returns:
            Scheduled job details
            
        Raises:
            NotFoundError: If job doesn't exist
        """
        # FIXED: Added input validation
        if not job_name or not job_name.strip():
            raise AppException("Job name cannot be empty", error_code="JOB_004")
            
        logger.info("fetching_scheduled_job", job_name=job_name)
        
        stmt = select(ScheduledJob).where(ScheduledJob.name == job_name)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            logger.warning("scheduled_job_not_found", job_name=job_name)
            raise NotFoundError(f"Scheduled job '{job_name}' not found", error_code="JOB_001")
            
        return ScheduledJobSchema.model_validate(job)

    async def list_scheduled_jobs(self) -> List[ScheduledJobSchema]:
        """List all scheduled jobs.
        
        Returns:
            List of scheduled jobs
        """
        logger.info("listing_scheduled_jobs")
        
        stmt = select(ScheduledJob)
        result = await self.db.execute(stmt)
        jobs = result.scalars().all()
        
        return [ScheduledJobSchema.model_validate(job) for job in jobs]

    async def update_job_status(self, job_name: str, payload: ScheduledJobUpdate) -> ScheduledJobSchema:
        """Enable/disable a scheduled job.
        
        Args:
            job_name: Name of the job to update
            payload: Update parameters
            
        Returns:
            Updated job details
            
        Raises:
            NotFoundError: If job doesn't exist
        """
        # FIXED: Added input validation
        if not job_name or not job_name.strip():
            raise AppException("Job name cannot be empty", error_code="JOB_004")
            
        logger.info("updating_job_status", job_name=job_name, enabled=payload.enabled)
        
        stmt = select(ScheduledJob).where(ScheduledJob.name == job_name)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            logger.warning("job_not_found_for_update", job_name=job_name)
            raise NotFoundError(f"Job '{job_name}' not found", error_code="JOB_001")
            
        # Update the job
        update_stmt = update(ScheduledJob).where(ScheduledJob.name == job_name).values(enabled=payload.enabled)
        await self.db.execute(update_stmt)
        await self.db.commit()
        
        # Refresh the job
        await self.db.refresh(job)
        
        logger.info("job_status_updated", job_name=job_name, enabled=payload.enabled)
        return ScheduledJobSchema.model_validate(job)

    async def list_job_executions(self, filters: JobExecutionFilterQuery) -> List[JobExecutionLogSchema]:
        """List job executions with filtering and pagination.
        
        Args:
            filters: Query parameters for filtering executions
            
        Returns:
            List of job execution logs
        """
        logger.info("listing_job_executions", filters=filters.model_dump())
        
        stmt = select(JobExecutionLog)
        
        if filters.job_name:
            stmt = stmt.where(JobExecutionLog.job_name == filters.job_name)
            
        if filters.status:
            # FIXED: Validate status values against allowed constants
            allowed_statuses = {"queued", "running", "completed", "failed"}
            if filters.status not in allowed_statuses:
                raise AppException(f"Invalid status: {filters.status}", error_code="JOB_005")
            stmt = stmt.where(JobExecutionLog.status == filters.status)
            
        stmt = stmt.order_by(JobExecutionLog.created_at.desc())
        stmt = stmt.limit(filters.limit).offset(filters.offset)
        
        result = await self.db.execute(stmt)
        executions = result.scalars().all()
        
        return [JobExecutionLogSchema.model_validate(exec) for exec in executions]