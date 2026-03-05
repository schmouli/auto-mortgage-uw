```python
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from mortgage_underwriting.modules.decision.models import DecisionAudit
from mortgage_underwriting.modules.decision.schemas import DecisionHistoryQueryParams

logger = structlog.get_logger()

class DecisionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_decision_history(self, application_id: int, query_params: DecisionHistoryQueryParams) -> List[DecisionAudit]:
        """
        Get paginated decision history for an application.
        
        Args:
            application_id: ID of the mortgage application
            query_params: Query parameters including skip and limit
            
        Returns:
            List of DecisionAudit objects
            
        FIXED: Implemented proper pagination with LIMIT/OFFSET
        FIXED: Enforced maximum limit of 100 to prevent abuse
        """
        # Cap the limit at 100 per page
        actual_limit = min(query_params.limit, 100)
        
        logger.info(
            "fetching_decision_history",
            application_id=application_id,
            skip=query_params.skip,
            limit=actual_limit
        )
        
        result = await self.db.execute(
            select(DecisionAudit)
            .where(DecisionAudit.application_id == application_id)
            .order_by(DecisionAudit.created_at.desc())
            .offset(query_params.skip)
            .limit(actual_limit)
        )
        
        return list(result.scalars().all())
```