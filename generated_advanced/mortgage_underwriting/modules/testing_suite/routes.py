from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.testing.schemas import (
    TestRunCreate,
    TestRunUpdate,
    TestRunResponse,
    TestCaseCreate,
    TestCaseUpdate,
    TestCaseResponse,
    TestCoverageReportCreate,
    TestCoverageReportUpdate,
    TestCoverageReportResponse
)
from mortgage_underwriting.modules.testing.services import TestRunService, TestCaseService, TestCoverageReportService

router = APIRouter(prefix="/api/v1/testing", tags=["Testing Suite"])


@router.post("/runs", response_model=TestRunResponse, status_code=status.HTTP_201_CREATED)
async def create_test_run(
    payload: TestRunCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new test run record."""
    service = TestRunService(db)
    try:
        return await service.create_run(payload)
    except Exception as e:
        # FIXED: Sanitized error response to prevent information leakage
        raise HTTPException(status_code=400, detail={"error": "Test run creation failed", "type": "TestRunCreationError"})


@router.put("/runs/{run_id}", response_model=TestRunResponse)
async def update_test_run(
    run_id: int,
    payload: TestRunUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """Update an existing test run record."""
    service = TestRunService(db)
    try:
        return await service.update_run(run_id, payload)
    except Exception as e:
        # FIXED: Sanitized error response to prevent information leakage
        raise HTTPException(status_code=400, detail={"error": "Test run update failed", "type": "TestRunUpdateError"})


@router.get("/runs/{run_id}", response_model=TestRunResponse)
async def get_test_run(
    run_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific test run by ID."""
    service = TestRunService(db)
    try:
        return await service.get_run(run_id)
    except Exception as e:
        # FIXED: Sanitized error response to prevent information leakage
        raise HTTPException(status_code=404, detail={"error": "Test run not found", "type": "TestRunNotFoundError"})


@router.get("/runs", response_model=List[TestRunResponse])
async def list_test_runs(
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_async_session),
):
    """List recent test runs with pagination."""
    service = TestRunService(db)
    return await service.list_runs(limit=limit, offset=offset)


@router.post("/cases", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
async def create_test_case(
    payload: TestCaseCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new test case result."""
    service = TestCaseService(db)
    try:
        return await service.create_case(payload)
    except Exception as e:
        # FIXED: Sanitized error response to prevent information leakage
        raise HTTPException(status_code=400, detail={"error": "Test case creation failed", "type": "TestCaseCreationError"})


@router.put("/cases/{case_id}", response_model=TestCaseResponse)
async def update_test_case(
    case_id: int,
    payload: TestCaseUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """Update an existing test case result."""
    service = TestCaseService(db)
    try:
        return await service.update_case(case_id, payload)
    except Exception as e:
        # FIXED: Sanitized error response to prevent information leakage
        raise HTTPException(status_code=400, detail={"error": "Test case update failed", "type": "TestCaseUpdateError"})


@router.get("/cases/{case_id}", response_model=TestCaseResponse)
async def get_test_case(
    case_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific test case by ID."""
    service = TestCaseService(db)
    try:
        return await service.get_case(case_id)
    except Exception as e:
        # FIXED: Sanitized error response to prevent information leakage
        raise HTTPException(status_code=404, detail={"error": "Test case not found", "type": "TestCaseNotFoundError"})


@router.get("/runs/{run_id}/cases", response_model=List[TestCaseResponse])
async def list_test_cases_for_run(
    run_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """List all test cases for a given run."""
    service = TestCaseService(db)
    return await service.list_cases_for_run(run_id)


@router.post("/coverage", response_model=TestCoverageReportResponse, status_code=status.HTTP_201_CREATED)
async def create_coverage_report(
    payload: TestCoverageReportCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new test coverage report."""
    service = TestCoverageReportService(db)
    try:
        return await service.create_report(payload)
    except Exception as e:
        # FIXED: Sanitized error response to prevent information leakage
        raise HTTPException(status_code=400, detail={"error": "Coverage report creation failed", "type": "CoverageReportCreationError"})


@router.put("/coverage/{report_id}", response_model=TestCoverageReportResponse)
async def update_coverage_report(
    report_id: int,
    payload: TestCoverageReportUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """Update an existing test coverage report."""
    service = TestCoverageReportService(db)
    try:
        return await service.update_report(report_id, payload)
    except Exception as e:
        # FIXED: Sanitized error response to prevent information leakage
        raise HTTPException(status_code=400, detail={"error": "Coverage report update failed", "type": "CoverageReportUpdateError"})


@router.get("/coverage/latest/{module_name}", response_model=TestCoverageReportResponse)
async def get_latest_coverage_report(
    module_name: str,
    db: AsyncSession = Depends(get_async_session),
):
    """Get the latest coverage report for a module."""
    service = TestCoverageReportService(db)
    report = await service.get_latest_report(module_name)
    if not report:
        # FIXED: Sanitized error response to prevent information leakage
        raise HTTPException(status_code=404, detail={"error": "Coverage report not found", "type": "CoverageReportNotFound"})
    return report


@router.get("/coverage", response_model=List[TestCoverageReportResponse])
async def list_coverage_reports(
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_async_session),
):
    """List recent coverage reports with pagination."""
    service = TestCoverageReportService(db)
    return await service.list_reports(limit=limit, offset=offset)