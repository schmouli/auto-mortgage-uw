from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from mortgage_underwriting.modules.testing.models import TestRun
from mortgage_underwriting.modules.testing.schemas import TestRunCreate, TestRunUpdate

logger = structlog.get_logger()

class TestRunService:
    """Service for managing test run records."""
    
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        
    async def create(self, payload: TestRunCreate) -> TestRun:
        """Create a new test run record.
        
        Args:
            payload: Test run creation data
            
        Returns:
            Created TestRun instance
        """
        logger.info("test_run_create", run_id=str(payload.run_id))
        
        try:
            instance = TestRun(**payload.model_dump())
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            
            logger.info("test_run_created", id=instance.id)
            return instance
        except Exception as e:
            logger.error("test_run_creation_failed", error=str(e))
            await self.db.rollback()
            raise
        
    async def get_by_run_id(self, run_id: UUID) -> Optional[TestRun]:
        """Get test run by its unique run ID.
        
        Args:
            run_id: Unique test run identifier
            
        Returns:
            TestRun instance or None if not found
        """
        logger.debug("fetching_test_run", run_id=str(run_id))
        
        try:
            stmt = select(TestRun).where(TestRun.run_id == str(run_id))
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("test_run_fetch_error", run_id=str(run_id), error=str(e))
            raise
        
    async def list_all(self, limit: int = 100, offset: int = 0) -> List[TestRun]:
        """List all test runs with pagination.
        
        Args:
            limit: Maximum number of records to return (max 100)
            offset: Number of records to skip
            
        Returns:
            List of TestRun instances
        """
        logger.debug("listing_test_runs", limit=limit, offset=offset)
        
        # Ensure limit doesn't exceed maximum allowed
        effective_limit = min(limit, 100)
        
        try:
            stmt = select(TestRun).order_by(TestRun.timestamp.desc()).offset(offset).limit(effective_limit)
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error("test_runs_list_error", error=str(e))
            raise
        
    async def update(self, run_id: UUID, payload: TestRunUpdate) -> Optional[TestRun]:
        """Update an existing test run record.
        
        Args:
            run_id: Unique test run identifier
            payload: Update data
            
        Returns:
            Updated TestRun instance or None if not found
        """
        logger.info("updating_test_run", run_id=str(run_id))
        
        try:
            instance = await self.get_by_run_id(run_id)
            if not instance:
                logger.warning("test_run_not_found_for_update", run_id=str(run_id))
                return None
                
            update_data = payload.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(instance, key, value)
                
            await self.db.commit()
            await self.db.refresh(instance)
            
            logger.info("test_run_updated", id=instance.id)
            return instance
        except Exception as e:
            logger.error("test_run_update_error", run_id=str(run_id), error=str(e))
            await self.db.rollback()
            raise