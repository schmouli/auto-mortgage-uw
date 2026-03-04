```python
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, text
from decimal import Decimal
import uuid

from .models import TestRun, TestCase
from .schemas import (
    TestRunCreateRequest,
    TestRunResponse,
    TestCaseCreateRequest,
    TestCaseUpdateRequest,
    TestCaseResponse,
    TestSuiteSummaryResponse
)
from ..common.exceptions import ResourceNotFoundError


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
        run.update_stats()
        run.completed_at = func.now()

        await self.db.commit()
        await self.db.refresh(run)
        return TestRunResponse.from_orm(run)

    async def add_test_case(self, run_id: str, data: TestCaseCreateRequest) -> TestCaseResponse:
        run = await self.get_test_run(run_id)
        new_case = TestCase(
            name=data.name,
            description=data.description,
            module=data.module,
            category=data.category,
            expected_result=data.expected_result,
            test_run_id=run.run_id
        )
        self.db.add(new_case)
        await self.db.commit()
        await self.db.refresh(new_case)
        return TestCaseResponse.from_orm(new_case)

    async def update_test_case(self, case_id: int, data: TestCaseUpdateRequest) -> TestCaseResponse:
        stmt = select(TestCase).where(TestCase.id == case_id)
        result = await self.db.execute(stmt)
        case = result.scalar_one_or_none()
        if not case:
            raise ResourceNotFoundError(f"Test case with ID {case_id} not found.")

        case.set_status(data.status, data.actual_result, data.execution_time_ms)
        await self.db.commit()
        await self.db.refresh(case)
        return TestCaseResponse.from_orm(case)

    async def get_suite_summary(self, suite_name: str) -> TestSuiteSummaryResponse:
        subquery = (
            select(TestRun.id.label("run_id"), TestRun.coverage_percentage)
            .where(TestRun.suite_name == suite_name)
        ).subquery()

        avg_coverage_stmt = select(func.avg(subquery.c.coverage_percentage)).scalar_subquery()
        success_rate_stmt = select(
            func.count(text("*")) /
            func.nullif(select(func.count(text("*"))).select_from(subquery), 0)
        ).scalar_subquery()

        count_stmt = select(func.count()).select_from(subquery)

        results = await self.db.execute(
            select(avg_coverage_stmt, success_rate_stmt, count_stmt)
        )

        row = results.fetchone()
        if not row:
            raise ResourceNotFoundError(f"No test runs found for suite '{suite_name}'")

        avg_cov, success_rate, count = row
        return TestSuiteSummaryResponse(
            suite_name=suite_name,
            run_count=count,
            average_coverage=avg_cov or Decimal('0'),
            success_rate=success_rate or Decimal('0')
        )
```

---