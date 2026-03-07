from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any, List
import uuid

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.modules.background_jobs.models import JobExecutionLog, ScheduledJob
from mortgage_underwriting.modules.background_jobs.schemas import (
    JobExecutionLogResponse,
    ScheduledJobResponse,
    ScheduledJobListResponse,
    JobTriggerRequest,
    JobTriggerResponse,
    JobStatusResponse
)
from mortgage_underwriting.modules.background_jobs.exceptions import JobNotFoundError, InvalidTaskNameError

logger = structlog.get_logger()

VALID_TASK_NAMES = {
    "send_document_reminder",
    "check_rate_expiry",
    "check_condition_due_dates",
    "generate_monthly_report",
    "cleanup_temp_uploads",
    "flag_fintrac_overdue"
}

class BackgroundJobsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def trigger_job(self, payload: JobTriggerRequest, user_id: Optional[int] = None) -> JobTriggerResponse:
        """Trigger a background job manually.
        
        Args:
            payload: Job trigger request with task name and parameters
            user_id: ID of user triggering the job (if authenticated)
            
        Returns:
            JobTriggerResponse with task details
            
        Raises:
            InvalidTaskNameError: If task name is not valid
        """
        logger.info(
            "job_trigger_requested",
            task_name=payload.task_name,
            user_id=user_id
        )
        
        if payload.task_name not in VALID_TASK_NAMES:
            logger.warning(
                "invalid_task_name_requested",
                task_name=payload.task_name
            )
            raise InvalidTaskNameError(f"Invalid task name: {payload.task_name}")
        
        # In a real implementation, this would enqueue the task with Celery
        # For now we'll simulate creating a log entry
        task_id = str(uuid.uuid4())
        scheduled_at = datetime.utcnow()
        
        job_log = JobExecutionLog(
            task_id=task_id,
            task_name=payload.task_name,
            status="pending",
            scheduled_at=scheduled_at,
            is_manual_trigger=True,
            triggered_by=user_id,
            args=payload.params
        )
        
        self.db.add(job_log)
        await self.db.commit()
        await self.db.refresh(job_log)
        
        logger.info(
            "job_triggered_successfully",
            task_id=task_id,
            task_name=payload.task_name
        )
        
        return JobTriggerResponse(
            task_id=task_id,
            status="queued",
            scheduled_at=scheduled_at
        )

    async def get_job_status(self, task_id: str) -> JobStatusResponse:
        """Get the status of a specific job execution.
        
        Args:
            task_id: Unique identifier of the task
            
        Returns:
            JobStatusResponse with current status information
            
        Raises:
            JobNotFoundError: If job with given task_id doesn't exist
        """
        # FIXED: Add input validation for task_id
        if not task_id or not isinstance(task_id, str) or len(task_id.strip()) == 0:
            logger.warning("invalid_task_id_provided", task_id=task_id)
            raise JobNotFoundError(f"Invalid task ID provided")
            
        logger.info(
            "job_status_requested",
            task_id=task_id
        )
        
        stmt = select(JobExecutionLog).where(JobExecutionLog.task_id == task_id)
        result = await self.db.execute(stmt)
        job_log = result.scalar_one_or_none()
        
        if not job_log:
            logger.warning(
                "job_not_found",
                task_id=task_id
            )
            raise JobNotFoundError(f"Job with task_id {task_id} not found")
            
        logger.info(
            "job_status_retrieved",
            task_id=task_id,
            status=job_log.status
        )
        
        return JobStatusResponse(
            task_id=job_log.task_id,
            task_name=job_log.task_name,
            status=job_log.status,
            started_at=job_log.started_at,
            completed_at=job_log.completed_at,
            result=job_log.result,
            error=job_log.error_message
        )

    async def get_scheduled_jobs(self) -> ScheduledJobListResponse:
        """Get all configured scheduled jobs.
        
        Returns:
            ScheduledJobListResponse with all scheduled jobs
        """
        logger.info("scheduled_jobs_list_requested")
        
        stmt = select(ScheduledJob).order_by(ScheduledJob.is_active.desc(), ScheduledJob.task_name)
        result = await self.db.execute(stmt)
        jobs = result.scalars().all()
        
        job_responses = [
            ScheduledJobResponse.model_validate(job) 
            for job in jobs
        ]
        
        logger.info(
            "scheduled_jobs_list_retrieved",
            count=len(job_responses)
        )
        
        return ScheduledJobListResponse(schedules=job_responses)

    async def enable_scheduled_job(self, task_name: str) -> ScheduledJobResponse:
        """Enable a scheduled job.
        
        Args:
            task_name: Name of the task to enable
            
        Returns:
            ScheduledJobResponse with updated job information
            
        Raises:
            JobNotFoundError: If job with given task_name doesn't exist
        """
        # FIXED: Add input validation for task_name
        if not task_name or not isinstance(task_name, str) or len(task_name.strip()) == 0:
            logger.warning("invalid_task_name_provided", task_name=task_name)
            raise JobNotFoundError(f"Invalid task name provided")
            
        logger.info(
            "scheduled_job_enable_requested",
            task_name=task_name
        )
        
        stmt = select(ScheduledJob).where(ScheduledJob.task_name == task_name)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            logger.warning(
                "scheduled_job_not_found",
                task_name=task_name
            )
            raise JobNotFoundError(f"Scheduled job {task_name} not found")
            
        job.is_active = True
        await self.db.commit()
        await self.db.refresh(job)
        
        logger.info(
            "scheduled_job_enabled",
            task_name=task_name
        )
        
        return ScheduledJobResponse.model_validate(job)