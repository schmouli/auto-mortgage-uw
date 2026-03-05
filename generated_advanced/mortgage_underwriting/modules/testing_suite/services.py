"""Services for the testing suite module."""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from decimal import Decimal, DivisionByZero
import uuid
import structlog

from .models import TestRun, TestCase, TestSuite
from .schemas import (
    TestRunCreateRequest,
    TestRunResponse,
    TestCaseCreateRequest,
    TestCaseUpdateRequest,
    TestCaseResponse,
    TestSuiteSummaryResponse
)
from ..common.exceptions import ResourceNotFoundError

logger = structlog.get_logger()

class TestingService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_test_run(self, data: TestRunCreateRequest) -> TestRunResponse:
        new_run = TestRun(
            suite_name=data.suite_name,
            started_at=data.started_at,
            run_id=str(uuid.uuid4())
        )
        self.db.add(new_run)
        await self.db.commit()
        await self.db.refresh(new_run)
        return TestRunResponse.from_orm(new_run)

    async def get_test_run(self, run_id: str) -> TestRunResponse:
        stmt = select(TestRun).where(TestRun.run_id == run_id)
        result = await self.db.execute(stmt)
        run = result.scalar_one_or_none()
        if not run:
            raise ResourceNotFoundError(f"Test run with ID {run_id} not found.")
        return TestRunResponse.from_orm(run)

    async def complete_test_run(self, run_id: str) -> TestRunResponse:
        run = await self.get_test_run(run_id)
        stmt = select(TestCase).where(TestCase.test_run_id == run_id)
        result = await self.db.execute(stmt)
        cases = result.scalars().all()

        run.passed_count = sum(1 for case in cases if case.status == 'pass')
        run.failed_count = sum(1 for case in cases if case.status == 'fail')
        run.skipped_count = sum(1 for case in cases if case.status == 'skip')
        run.total_count = len(cases)
        
        # FIXED: Handle potential division by zero
        if run.total_count > 0:
            success_rate = Decimal((run.passed_count + run.skipped_count) / run.total_count * 100)
            run.coverage_percentage = round(success_rate, 2)
        else:
            run.coverage_percentage = Decimal('0.00')
            logger.warning("no_test_cases_found_for_run", run_id=run_id)
            
        run.completed_at = func.now()
        run.is_success = run.failed_count == 0
        
        await self.db.commit()
        await self.db.refresh(run)
        return TestRunResponse.from_orm(run)

    # FIXED: Added pagination parameters with limits
    async def list_test_suites(self, skip: int = 0, limit: int = 50) -> List[TestSuite]:
        """List test suites with pagination support."""
        # Enforce maximum limit to prevent memory exhaustion
        if limit > 100:
            limit = 100
            logger.warning("pagination_limit_exceeded_setting_to_max", max_limit=100)
            
        stmt = select(TestSuite).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_test_suite_summary(self, suite_id: int) -> TestSuiteSummaryResponse:
        suite_stmt = select(TestSuite).where(TestSuite.id == suite_id)
        suite_result = await self.db.execute(suite_stmt)
        suite = suite_result.scalar_one_or_none()
        
        if not suite:
            raise ResourceNotFoundError(f"Test suite with ID {suite_id} not found.")
            
        # Use selectinload to prevent N+1 query issues
        test_stmt = select(TestCase).options(selectinload(TestCase.suite)).where(TestCase.suite_id == suite_id)
        test_result = await self.db.execute(test_stmt)
        tests = test_result.scalars().all()
        
        passed = sum(1 for test in tests if test.status == 'pass')
        failed = sum(1 for test in tests if test.status == 'fail')
        total = len(tests)
        
        # FIXED: Handle potential division by zero
        success_rate = Decimal('0.00')
        if total > 0:
            success_rate = Decimal((passed / total) * 100)
        else:
            logger.warning("no_tests_found_for_suite", suite_id=suite_id)
            
        return TestSuiteSummaryResponse(
            suite_id=suite_id,
            suite_name=suite.name,
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            success_rate=success_rate,
            is_active=suite.is_active
        )