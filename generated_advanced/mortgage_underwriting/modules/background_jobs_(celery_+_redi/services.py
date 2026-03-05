import structlog
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from sqlalchemy.orm import selectinload
from .models import BackgroundJob
from .exceptions import JobExecutionError, JobNotFoundError
from .schemas import BackgroundJobResponse
from mortgage_underwriting.common.email_service import send_email  # Hypothetical email service
from mortgage_underwriting.common.storage import delete_old_files  # Hypothetical file cleanup utility


logger = structlog.get_logger(__name__)


class BackgroundJobService:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db = db_session

    async def get_job_by_name(self, job_name: str) -> BackgroundJob:
        result = await self.db.execute(select(BackgroundJob).where(BackgroundJob.job_name == job_name))
        job = result.scalar_one_or_none()
        if not job:
            raise JobNotFoundError(f"Job '{job_name}' not found.")
        return job

    async def list_jobs(self, skip: int = 0, limit: int = 50) -> List[BackgroundJob]:
        # FIXED: Added pagination support with skip/limit
        # FIXED: Added selectinload to prevent N+1 queries
        if limit > 100:
            limit = 100  # Cap limit at 100 per requirements
            
        result = await self.db.execute(
            select(BackgroundJob)
            .options(selectinload(BackgroundJob.result_log))  # FIXED: Prevent N+1 queries
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def update_job_run_info(self, job_name: str, success: bool = True) -> None:
        # FIXED: Added proper exception handling
        try:
            stmt = (
                update(BackgroundJob)
                .where(BackgroundJob.job_name == job_name)
                .values(
                    last_run_at=datetime.utcnow(),
                    status="success" if success else "failed",
                    updated_at=datetime.utcnow()
                )
            )
            await self.db.execute(stmt)
            await self.db.commit()
            logger.info("Job run info updated", job_name=job_name, success=success)
        except Exception as e:
            logger.error("Failed to update job run info", job_name=job_name, error=str(e))
            await self.db.rollback()
            raise JobExecutionError(f"Failed to update job run info: {str(e)}")

    async def execute_file_cleanup_job(self) -> Dict[str, Any]:
        """Execute the file cleanup job with proper error handling."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            deleted_count = delete_old_files(cutoff_date)
            
            logger.info("File cleanup job completed", files_deleted=deleted_count, cutoff_date=cutoff_date.isoformat())
            return {
                "status": "success",
                "files_deleted": deleted_count,
                "cutoff_date": cutoff_date.isoformat()
            }
        except Exception as e:
            logger.error("File cleanup job failed", error=str(e))
            raise JobExecutionError(f"File cleanup failed: {str(e)}")

    async def execute_notification_job(self) -> Dict[str, Any]:
        """Execute notification job with proper error handling."""
        try:
            # Simulate sending notifications
            recipients = ["admin@example.com"]
            subject = "Daily Report"
            body = "This is your daily system report."
            
            for recipient in recipients:
                send_email(recipient, subject, body)
                
            logger.info("Notification job completed", recipients_count=len(recipients))
            return {
                "status": "success",
                "recipients_count": len(recipients)
            }
        except Exception as e:
            logger.error("Notification job failed", error=str(e))
            raise JobExecutionError(f"Notification job failed: {str(e)}")
```

```