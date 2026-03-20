from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.testing.models import TestRun, TestCase, TestCoverageReport
from mortgage_underwriting.modules.testing.schemas import (
    TestRunCreate,
    TestRunUpdate,
    TestCaseCreate,
    TestCaseUpdate,
    TestCoverageReportCreate,
    TestCoverageReportUpdate
)

logger = structlog.get_logger()


class TestRunService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_run(self, payload: TestRunCreate) -> TestRun:
        """Create a new test run record."""
        # FIXED: Removed sensitive data from logs, only log safe identifiers
        logger.info("test_run_create", module=payload.module_name, suite=payload.test_suite_type)
        instance = TestRun(**payload.model_dump(exclude_unset=True))
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update_run(self, run_id: int, payload: TestRunUpdate) -> TestRun:
        """Update an existing test run record."""
        # FIXED: Removed sensitive data from logs
        logger.info("test_run_update", run_id=run_id)
        stmt = select(TestRun).where(TestRun.id == run_id)
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        if not instance:
            raise AppException(f"TestRun {run_id} not found")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(instance, key, value)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def get_run(self, run_id: int) -> TestRun:
        """Get a specific test run by ID."""
        # FIXED: Removed sensitive data from logs
        logger.debug("test_run_get", run_id=run_id)
        stmt = select(TestRun).where(TestRun.id == run_id).options(selectinload(TestRun.test_cases))
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        if not instance:
            raise AppException(f"TestRun {run_id} not found")
        return instance

    async def list_runs(self, limit: int = 50, offset: int = 0) -> List[TestRun]:
        """List recent test runs with pagination."""
        # FIXED: Removed sensitive data from logs
        logger.debug("test_run_list", limit=limit, offset=offset)
        stmt = select(TestRun).order_by(TestRun.started_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class TestCaseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_case(self, payload: TestCaseCreate) -> TestCase:
        """Create a new test case result."""
        # FIXED: Removed sensitive error details from logs, only log safe identifiers
        logger.info("test_case_create", test_name=payload.test_name)
        instance = TestCase(**payload.model_dump(exclude_unset=True))
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update_case(self, case_id: int, payload: TestCaseUpdate) -> TestCase:
        """Update an existing test case result."""
        # FIXED: Removed sensitive data from logs
        logger.info("test_case_update", case_id=case_id)
        stmt = select(TestCase).where(TestCase.id == case_id)
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        if not instance:
            raise AppException(f"TestCase {case_id} not found")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(instance, key, value)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def get_case(self, case_id: int) -> TestCase:
        """Get a specific test case by ID."""
        # FIXED: Removed sensitive data from logs
        logger.debug("test_case_get", case_id=case_id)
        stmt = select(TestCase).where(TestCase.id == case_id)
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        if not instance:
            raise AppException(f"TestCase {case_id} not found")
        return instance

    async def list_cases_for_run(self, run_id: int) -> List[TestCase]:
        """List all test cases for a given run."""
        # FIXED: Removed sensitive data from logs
        logger.debug("test_case_list_for_run", run_id=run_id)
        stmt = select(TestCase).where(TestCase.run_id == run_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class TestCoverageReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_report(self, payload: TestCoverageReportCreate) -> TestCoverageReport:
        """Create a new test coverage report."""
        # FIXED: Removed sensitive data from logs
        logger.info("coverage_report_create", module=payload.module_name)
        instance = TestCoverageReport(**payload.model_dump(exclude_unset=True))
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update_report(self, report_id: int, payload: TestCoverageReportUpdate) -> TestCoverageReport:
        """Update an existing test coverage report."""
        # FIXED: Removed sensitive data from logs
        logger.info("coverage_report_update", report_id=report_id)
        stmt = select(TestCoverageReport).where(TestCoverageReport.id == report_id)
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        if not instance:
            raise AppException(f"TestCoverageReport {report_id} not found")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(instance, key, value)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def get_latest_report(self, module_name: str) -> Optional[TestCoverageReport]:
        """Get the latest coverage report for a module."""
        # FIXED: Removed sensitive data from logs
        logger.debug("coverage_report_get_latest", module=module_name)
        stmt = (
            select(TestCoverageReport)
            .where(TestCoverageReport.module_name == module_name)
            .order_by(TestCoverageReport.reported_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_reports(self, limit: int = 50, offset: int = 0) -> List[TestCoverageReport]:
        """List recent coverage reports with pagination."""
        # FIXED: Removed sensitive data from logs
        logger.debug("coverage_report_list", limit=limit, offset=offset)
        stmt = select(TestCoverageReport).order_by(TestCoverageReport.reported_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())