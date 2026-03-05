"""Routes for the testing suite module."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import structlog

from .services import TestingService
from .schemas import (
    TestRunCreateRequest,
    TestRunResponse,
    TestCaseCreateRequest,
    TestCaseUpdateRequest,
    TestCaseResponse,
    TestSuiteSummaryResponse
)
from ..common.exceptions import ResourceNotFoundError
from ..common.database import get_async_session

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/testing", tags=["Testing"])

async def get_testing_service(db: AsyncSession = Depends(get_async_session)) -> TestingService:
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
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ResourceNotFoundError as e:  # FIXED: Catch specific exceptions
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("unexpected_error_in_start_test_run", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


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
        Detailed information about the test run.
    """
    try:
        return await service.get_test_run(run_id)
    except ResourceNotFoundError as e:  # FIXED: Catch specific exceptions
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("unexpected_error_in_get_test_run", error=str(e), run_id=run_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/suites", response_model=List[TestSuiteSummaryResponse], summary="List Test Suites")
async def list_test_suites(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),  # FIXED: Added validation with max limit
    service: TestingService = Depends(get_testing_service)
):
    """
    Lists available test suites with pagination.

    Args:
        skip: Number of records to skip
        limit: Number of records to return (max 100)

    Returns:
        List of test suite summaries.
    """
    try:
        suites = await service.list_test_suites(skip=skip, limit=limit)
        return suites
    except Exception as e:
        logger.error("unexpected_error_in_list_test_suites", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

```