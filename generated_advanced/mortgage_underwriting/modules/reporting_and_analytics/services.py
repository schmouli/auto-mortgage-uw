import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from .models import Report
from .schemas import ReportCreate, ReportUpdate

logger = structlog.get_logger()


class ReportingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_reports_list(self, skip: int = 0, limit: int = 100) -> List[Report]:
        """
        Retrieve paginated list of reports.
        
        Args:
            skip (int): Number of items to skip
            limit (int): Maximum number of items to return (max 100)
            
        Returns:
            List[Report]: Paginated list of reports
        """
        logger.info("fetching_reports_list", skip=skip, limit=limit)
        query = select(Report).offset(skip).limit(min(limit, 100))
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_report(self, payload: ReportCreate) -> Report:
        logger.info("creating_report", report_type=payload.report_type)
        instance = Report(**payload.model_dump())
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update_report(self, report_id: int, payload: ReportUpdate) -> Report:
        logger.info("updating_report", report_id=report_id)
        query = select(Report).where(Report.id == report_id)
        result = await self.db.execute(query)
        instance = result.scalar_one_or_none()
        
        if not instance:
            raise ValueError("Report not found")
            
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(instance, key, value)
            
        await self.db.commit()
        await self.db.refresh(instance)
        return instance
```

```