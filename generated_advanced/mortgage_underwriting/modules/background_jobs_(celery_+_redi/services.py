from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
import json

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.background_jobs.models import BackgroundJob, JobSchedule
from mortgage_underwriting.modules.background_jobs.schemas import JobTriggerRequest, JobTriggerResponse, JobStatusResponse, JobExecutionStatus

logger = structlog.get_logger()

class BackgroundJobService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def trigger_job(self, job_name: str, payload: JobTriggerRequest) -> JobTriggerResponse:
        # FIXED: Added validation for job_name length and characters
        if not job_name or len(job_name) > 100 or not job_name.replace('_', '').replace('-', '').isalnum():
            raise AppException("Invalid job name", error_code="JOB_003")
            
        logger.info("trigger_job", job_name=job_name, force=payload.force)
        
        # Check if job exists in configuration
        schedule_result = await self.db.execute(select(JobSchedule).where(JobSchedule.job_name == job_name))
        schedule: Optional[JobSchedule] = schedule_result.scalar_one_or_none()
        if not schedule:
            raise AppException(f"Job '{job_name}' not configured", error_code="JOB_001")
        
        # FIXED: Validate schedule is enabled unless force=true
        if not schedule.is_enabled and not payload.force:
            raise AppException(f"Job '{job_name}' is disabled", error_code="JOB_004")
        
        # Generate mock task ID (in real implementation would integrate with Celery)
        task_id = f"task_{int(datetime.now().timestamp() * 1000000)}"
        
        # FIXED: Sanitize params to prevent injection
        params_str = None
        if payload.params:
            try:
                params_str = json.dumps(payload.params, separators=(',', ':'))
            except (TypeError, ValueError) as e:
                raise AppException("Invalid params format", error_code="JOB_005")
        
        # Create job record
        job_record = BackgroundJob(
            job_name=job_name,
            task_id=task_id,
            status="queued",
            params=params_str,
            created_at=datetime.now()
        )
        
        self.db.add(job_record)
        await self.db.commit()
        await self.db.refresh(job_record)
        
        return JobTriggerResponse(
            job_name=job_name,
            task_id=task_id,
            status="queued",
            queued_at=job_record.created_at
        )

    async def get_job_status(self, job_name: str) -> JobStatusResponse:
        # FIXED: Added validation for job_name
        if not job_name or len(job_name) > 100 or not job_name.replace('_', '').replace('-', '').isalnum():
            raise AppException("Invalid job name", error_code="JOB_003")
            
        logger.info("get_job_status", job_name=job_name)
        
        # Get schedule info
        schedule_result = await self.db.execute(select(JobSchedule).where(JobSchedule.job_name == job_name))
        schedule: Optional[JobSchedule] = schedule_result.scalar_one_or_none()
        if not schedule:
            raise AppException(f"Job '{job_name}' not configured", error_code="JOB_001")
        
        # Get latest execution
        job_result = await self.db.execute(
            select(BackgroundJob)
            .where(BackgroundJob.job_name == job_name)
            .order_by(BackgroundJob.created_at.desc())
            .limit(1)
        )
        job: Optional[BackgroundJob] = job_result.scalar_one_or_none()
        
        last_execution: Optional[JobExecutionStatus] = None
        if job:
            last_execution = JobExecutionStatus(
                task_id=job.task_id,
                status=job.status,
                started_at=job.started_at,
                completed_at=job.completed_at,
                duration_seconds=Decimal(str(job.duration_seconds)) if job.duration_seconds else None,
                records_processed=job.records_processed,
                error_code=job.error_code,
                error_message=job.error_message
            )
        
        return JobStatusResponse(
            job_name=job_name,
            is_enabled=schedule.is_enabled,
            schedule=schedule.schedule_expression,
            last_execution=last_execution,
            next_scheduled_run=schedule.next_run_time
        )