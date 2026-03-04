```python
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from .models import BackgroundJob
from .exceptions import JobExecutionError, JobNotFoundError
from common.email_service import send_email  # Hypothetical email service
from common.storage import delete_old_files  # Hypothetical file cleanup utility
from common.utils import get_db_session  # Hypothetical DB session getter


logger = logging.getLogger(__name__)


class BackgroundJobService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_job_by_name(self, job_name: str) -> BackgroundJob:
        result = await self.db.execute(select(BackgroundJob).where(BackgroundJob.job_name == job_name))
        job = result.scalar_one_or_none()
        if not job:
            raise JobNotFoundError(f"Job '{job_name}' not found.")
        return job

    async def update_job_run_info(self, job_name: str, success: bool = True):
        stmt = (
            update(BackgroundJob)
            .where(BackgroundJob.job_name == job_name)
            .values(
                last_run_at=datetime.utcnow(),
                next_run_at=self._calculate_next_run(job_name),  # Simplified placeholder
                updated_at=datetime.utcnow()
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

    def _calculate_next_run(self, job_name: str) -> Optional[datetime]:
        # Placeholder implementation; real version would parse cron expressions
        return datetime.utcnow() + timedelta(hours=24)

    async def send_document_reminder(self):
        try:
            logger.info("Starting send_document_reminder job")
            # Logic to fetch clients with outstanding documents
            clients = await self._fetch_outstanding_document_clients()
            for client in clients:
                await send_email(
                    to=client["email"],
                    subject="Document Reminder",
                    body=f"Dear {client['name']}, please submit your pending documents."
                )
            await self.update_job_run_info("send_document_reminder")
            logger.info("Completed send_document_reminder job successfully")
        except Exception as e:
            logger.error(f"Failed to execute send_document_reminder: {str(e)}")
            raise JobExecutionError("send_document_reminder", str(e))

    async def check_rate_expiry(self):
        try:
            logger.info("Starting check_rate_expiry job")
            # Logic to flag expired lender product rates
            expired_products = await self._find_expired_lender_rates()
            for product in expired_products:
                await self._flag_product_as_expired(product["id"])
            await self.update_job_run_info("check_rate_expiry")
            logger.info("Completed check_rate_expiry job successfully")
        except Exception as e:
            logger.error(f"Failed to execute check_rate_expiry: {str(e)}")
            raise JobExecutionError("check_rate_expiry", str(e))

    async def check_condition_due_dates(self):
        try:
            logger.info("Starting check_condition_due_dates job")
            # Logic to flag overdue lender conditions
            overdue_conditions = await self._find_overdue_conditions()
            for condition in overdue_conditions:
                await self._flag_condition_as_overdue(condition["id"])
            await self.update_job_run_info("check_condition_due_dates")
            logger.info("Completed check_condition_due_dates job successfully")
        except Exception as e:
            logger.error(f"Failed to execute check_condition_due_dates: {str(e)}")
            raise JobExecutionError("check_condition_due_dates", str(e))

    async def generate_monthly_report(self):
        try:
            logger.info("Starting generate_monthly_report job")
            # Logic to generate and store monthly report
            report_data = await self._compile_monthly_data()
            await self._store_report(report_data)
            await self.update_job_run_info("generate_monthly_report")
            logger.info("Completed generate_monthly_report job successfully")
        except Exception as e:
            logger.error(f"Failed to execute generate_monthly_report: {str(e)}")
            raise JobExecutionError("generate_monthly_report", str(e))

    async def cleanup_temp_uploads(self):
        try:
            logger.info("Starting cleanup_temp_uploads job")
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            upload_dir = Path("/uploads/temp")
            deleted_count = delete_old_files(upload_dir, cutoff_time)
            logger.info(f"Deleted {deleted_count} temporary files older than 24 hours")
            await self.update_job_run_info("cleanup_temp_uploads")
            logger.info("Completed cleanup_temp_uploads job successfully")
        except Exception as e:
            logger.error(f"Failed to execute cleanup_temp_uploads: {str(e)}")
            raise JobExecutionError("cleanup_temp_uploads", str(e))

    async def flag_fintrac_overdue(self):
        try:
            logger.info("Starting flag_fintrac_overdue job")
            # Logic to flag applications missing FINTRAC verification
            overdue_apps = await self._find_fintrac_overdue_applications()
            for app in overdue_apps:
                await self._flag_application_fintrac_overdue(app["id"])
            await self.update_job_run_info("flag_fintrac_overdue")
            logger.info("Completed flag_fintrac_overdue job successfully")
        except Exception as e:
            logger.error(f"Failed to execute flag_fintrac_overdue: {str(e)}")
            raise JobExecutionError("flag_fintrac_overdue", str(e))

    # Private helper methods (would connect to actual business logic/data layers)
    async def _fetch_outstanding_document_clients(self) -> List[Dict[str, Any]]:
        # Placeholder for fetching clients with missing docs
        return [{"email": "client@example.com", "name": "John Doe"}]

    async def _find_expired_lender_rates(self) -> List[Dict[str, Any]]:
        # Placeholder for finding expired rates
        return [{"id": 123}]

    async def _flag_product_as_expired(self, product_id: int):
        # Placeholder for flagging a product
        pass

    async def _find_overdue_conditions(self) -> List[Dict[str, Any]]:
        # Placeholder for finding overdue conditions
        return [{"id": 456}]

    async def _flag_condition_as_overdue(self, condition_id: int):
        # Placeholder for flagging a condition
        pass

    async def _compile_monthly_data(self) -> Dict[str, Any]:
        # Placeholder for compiling monthly data
        return {"total_mortgages": 100, "average_rate": "3.5%"}

    async def _store_report(self, data: Dict[str, Any]):
        # Placeholder for storing report
        pass

    async def _find_fintrac_overdue_applications(self) -> List[Dict[str, Any]]:
        # Placeholder for finding overdue FINTRAC applications
        return [{"id": 789}]

    async def _flag_application_fintrac_overdue(self, application_id: int):
        # Placeholder for flagging an application
        pass
```