from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sql_func
import structlog

from mortgage_underwriting.common.exceptions import NotFoundError
from mortgage_underwriting.modules.scheduled_jobs.models import ScheduledJobExecution
from mortgage_underwriting.modules.scheduled_jobs.schemas import JobExecutionDetail, JobExecutionBase, JobExecutionListResponse

logger = structlog.get_logger()


class ScheduledJobService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_executions(
        self,
        task_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> JobExecutionListResponse:
        """List recent job executions with optional filtering."""
        logger.info("listing_job_executions", task_name=task_name, status=status, limit=limit, offset=offset)
        
        try:
            query = select(ScheduledJobExecution)
            
            if task_name:
                query = query.where(ScheduledJobExecution.task_name == task_name)
            if status:
                query = query.where(ScheduledJobExecution.status == status)
                
            # Get total count
            count_query = select(sql_func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total = total_result.scalar_one_or_none() or 0
            
            # Apply pagination
            query = query.order_by(ScheduledJobExecution.started_at.desc()).offset(offset).limit(limit)
            result = await self.db.execute(query)
            executions = result.scalars().all()
            
            items = [
                JobExecutionBase.model_validate(execution) for execution in executions
            ]
            
            return JobExecutionListResponse(
                items=items,
                total=total,
                limit=limit,
                offset=offset
            )
        except Exception as e:
            logger.error("error_listing_job_executions", error=str(e))
            raise

    async def get_execution_detail(self, job_id: str) -> JobExecutionDetail:
        """Get detailed information about a specific job execution."""
        logger.info("getting_job_execution_detail", job_id=job_id)
        
        try:
            query = select(ScheduledJobExecution).where(ScheduledJobExecution.job_id == job_id)
            result = await self.db.execute(query)
            execution = result.scalar_one_or_none()
            
            if not execution:
                logger.warning("job_execution_not_found", job_id=job_id)
                raise NotFoundError(f"Job execution {job_id} not found")
                
            return JobExecutionDetail.model_validate(execution)
        except NotFoundError:
            # Re-raise known exceptions without modification
            raise
        except Exception as e:
            logger.error("error_getting_job_execution_detail", job_id=job_id, error=str(e))
            raise