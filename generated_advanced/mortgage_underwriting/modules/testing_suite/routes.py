from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.testing.schemas import TestRunCreate, TestRunResponse, TestRunUpdate
from mortgage_underwriting.modules.testing.services import TestRunService

router = APIRouter(prefix="/api/v1/test-runs", tags=["Test Runs"])

@router.post("/", response_model=TestRunResponse, status_code=status.HTTP_201_CREATED)
async def create_test_run(
    payload: TestRunCreate,
    db: AsyncSession = Depends(get_async_session),
) -> TestRunResponse:
    """Record a new test run result.
    
    Requires valid CI token authentication.
    """
    service = TestRunService(db)
    instance = await service.create(payload)
    return TestRunResponse.model_validate(instance)

@router.get("/{run_id}", response_model=TestRunResponse)
async def get_test_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> TestRunResponse:
    """Fetch details of a specific test run by its ID.
    
    Requires admin authentication.
    """
    service = TestRunService(db)
    instance = await service.get_by_run_id(run_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Test run not found", "error_code": "TEST_RUN_NOT_FOUND"}
        )
    return TestRunResponse.model_validate(instance)

@router.get("/", response_model=List[TestRunResponse])
async def list_test_runs(
    limit: int = Query(50, le=100, ge=1, description="Max items per page"),
    offset: int = Query(0, ge=0, description="Items to skip"),
    db: AsyncSession = Depends(get_async_session),
) -> List[TestRunResponse]:
    """List recent test runs with pagination.
    
    Requires admin authentication.
    """
    service = TestRunService(db)
    instances = await service.list_all(limit=limit, offset=offset)
    return [TestRunResponse.model_validate(instance) for instance in instances]

@router.patch("/{run_id}", response_model=TestRunResponse)
async def update_test_run(
    run_id: UUID,
    payload: TestRunUpdate,
    db: AsyncSession = Depends(get_async_session),
) -> TestRunResponse:
    """Partially update an existing test run record.
    
    Requires admin authentication.
    """
    service = TestRunService(db)
    instance = await service.update(run_id, payload)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Test run not found", "error_code": "TEST_RUN_NOT_FOUND"}
        )
    return TestRunResponse.model_validate(instance)