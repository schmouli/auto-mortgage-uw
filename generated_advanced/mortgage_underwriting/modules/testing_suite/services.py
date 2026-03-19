from datetime import datetime, timedelta
from hashlib import sha256
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.common.config import settings
from mortgage_underwriting.modules.testing.models import TestScenario, TestDataRun
from mortgage_underwriting.modules.testing.schemas import (
    TestScenarioCreate,
    TestScenarioResponse,
    TestDataSeedRequest,
    TestDataSeedResponse,
    TestDataCleanupRequest,
    TestDataCleanupResponse
)

logger = structlog.get_logger()


class TestScenarioService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, payload: TestScenarioCreate) -> TestScenarioResponse:
        logger.info("test_scenario_create", name=payload.name)
        try:
            instance = TestScenario(**payload.model_dump())
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return TestScenarioResponse.model_validate(instance)
        except IntegrityError as e:
            await self.db.rollback()
            logger.error("test_scenario_create_failed", error=str(e))
            raise AppException("TEST_SCENARIO_CREATE_FAILED", "Failed to create test scenario") from e


class TestDataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def seed_data(self, payload: TestDataSeedRequest, user_id: Optional[int]) -> TestDataSeedResponse:
        logger.info("test_data_seed_start", scenario=payload.scenario, user_id=user_id)
        
        # Verify scenario exists
        stmt = select(TestScenario).where(TestScenario.name == payload.scenario)
        result = await self.db.execute(stmt)
        scenario = result.scalar_one_or_none()
        
        if not scenario:
            logger.warning("invalid_test_scenario", scenario_name=payload.scenario)
            raise AppException("INVALID_SCENARIO", f"Scenario '{payload.scenario}' not found")
        
        # Use scenario count if not overridden
        entity_count = payload.count if payload.count is not None else scenario.count
        
        # Generate cleanup token
        cleanup_token = str(uuid4())
        cleanup_token_hash = sha256(cleanup_token.encode()).hexdigest()
        test_run_id = f"td_{uuid4().hex[:8]}"
        
        # In real implementation, this would call other services to create actual test data
        # Here we just record the intent
        test_run = TestDataRun(
            id=test_run_id,
            scenario_name=payload.scenario,
            created_entities=entity_count,
            cleanup_token_hash=cleanup_token_hash,
            created_by_user_id=user_id,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=getattr(settings, 'TEST_DATA_EXPIRY_HOURS', 24))
        )
        
        self.db.add(test_run)
        await self.db.commit()
        
        logger.info("test_data_seeded", test_run_id=test_run_id)
        
        return TestDataSeedResponse(
            scenario=payload.scenario,
            created_applications=entity_count,
            test_data_id=test_run_id,
            cleanup_token=cleanup_token
        )

    async def cleanup_data(self, payload: TestDataCleanupRequest, user_id: Optional[int]) -> TestDataCleanupResponse:
        logger.info("test_data_cleanup_start", user_id=user_id)
        
        cleanup_token_hash = sha256(payload.cleanup_token.encode()).hexdigest()
        
        # Find the test run
        stmt = select(TestDataRun).where(TestDataRun.cleanup_token_hash == cleanup_token_hash)
        result = await self.db.execute(stmt)
        test_run = result.scalar_one_or_none()
        
        if not test_run:
            logger.warning("invalid_cleanup_token")
            raise AppException("INVALID_CLEANUP_TOKEN", "Invalid or expired cleanup token")
        
        # Check if user has permission to clean up this data
        if test_run.created_by_user_id and user_id and test_run.created_by_user_id != user_id:
            logger.warning("unauthorized_cleanup_attempt", user_id=user_id, owner_id=test_run.created_by_user_id)
            raise AppException("UNAUTHORIZED_CLEANUP", "You are not authorized to clean up this test data")
        
        # In real implementation, this would delete associated entities
        # For now, we'll just mark it as cleaned up
        deleted_count = test_run.created_entities
        await self.db.delete(test_run)
        await self.db.commit()
        
        logger.info("test_data_cleaned_up", deleted_entities=deleted_count)
        
        return TestDataCleanupResponse(
            deleted_entities=deleted_count,
            message=f"Successfully deleted {deleted_count} entities"
        )