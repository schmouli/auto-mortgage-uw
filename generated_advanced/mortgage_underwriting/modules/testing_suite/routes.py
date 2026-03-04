```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from .services import TestingService
from .schemas import (
    TestRunCreateRequest,
    TestRunResponse,
    TestCaseCreateRequest,
    TestCaseUpdateRequest,
    TestCaseResponse,
    TestSuiteSummaryResponse
)
from ..database.session import get_db_async

router = APIRouter(prefix="/testing", tags=["Testing"])

async def get_testing_service(db: AsyncSession = Depends(get_db_async)) -> TestingService:
    return TestingService(db)


@router.post("/runs", response_model=TestRunResponse, summary="Start a New Test Run")
async def start_test_run(
    data: TestRunCreateRequest,
    service: TestingService = Depends(get_testing_service)
):
    """
    Starts a new test run session.

    Returns:
        The newly created test run object including its unique identifier.
    """
    try:
        return await service.create_test_run(data)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/runs/{run_id}", response_model=TestRunResponse, summary="Get Test Run Details")
async def get_test_run_details(
    run_id: str,
    service: TestingService = Depends(get_testing_service)
):
    """
    Retrieves details about a specific test run.

    Args:
        run_id: Unique identifier for the test run.

    Returns:
        Detailed information about the requested test run.
    """
    try:
        return await service.get_test_run(run_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/runs/{run_id}/complete", response_model=TestRunResponse, summary="Complete Test Run")
async def complete_test_run(
    run_id: str,
    service: TestingService = Depends(get_testing_service)
):
    """
    Marks a test run as completed and calculates final statistics.

    Args:
        run_id: Unique identifier for the test run.

    Returns:
        Updated test run object with completion time and metrics.
    """
    try:
        return await service.complete_test_run(run_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/runs/{run_id}/cases", response_model=TestCaseResponse, summary="Add Test Case to Run")
async def add_test_case_to_run(
    run_id: str,
    data: TestCaseCreateRequest,
    service: TestingService = Depends(get_testing_service)
):
    """
    Adds a new test case to an existing test run.

    Args:
        run_id: Unique identifier for the test run.
        data: Test case creation parameters.

    Returns:
        Newly added test case object.
    """
    try:
        return await service.add_test_case(run_id, data)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/cases/{case_id}", response_model=TestCaseResponse, summary="Update Test Case Result")
async def update_test_case_result(
    case_id: int,
    data: TestCaseUpdateRequest,
    service: TestingService = Depends(get_testing_service)
):
    """
    Updates the outcome of a test case.

    Args:
        case_id: Internal database ID of the test case.
        data: Update payload containing actual result and status.

    Returns:
        Updated test case object.
    """
    try:
        return await service.update_test_case(case_id, data)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/suites/{suite_name}/summary", response_model=TestSuiteSummaryResponse, summary="Get Suite Summary")
async def get_suite_summary(
    suite_name: str,
    service: TestingService = Depends(get_testing_service)
):
    """
    Provides aggregated testing metrics for a given test suite.

    Args:
        suite_name: Name of the test suite (e.g., underwriting).

    Returns:
        Aggregated summary including average coverage and success rate.
    """
    try:
        return await service.get_suite_summary(suite_name)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

---