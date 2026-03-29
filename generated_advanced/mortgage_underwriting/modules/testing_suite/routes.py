from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, status

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.auth.dependencies import get_current_user, get_admin_user
from mortgage_underwriting.modules.auth.models import User
from mortgage_underwriting.modules.testing.schemas import (

    TestScenarioCreate, TestScenarioUpdate, TestScenarioResponse,
    TestExecuteRequest, TestExecutionResponse, TestExecutionDetail,
    TestFixtureCreate, TestFixtureUpdate, TestFixtureResponse, TestFixtureData
)
from mortgage_underwriting.modules.testing.services import (
    TestScenarioService, TestExecutionService, TestFixtureService
)
from mortgage_underwriting.modules.testing.exceptions import TestManagementError

router = APIRouter(prefix="/api/v1/test", tags=["Testing Suite"])


@router.post("/scenarios", 
             response_model=TestScenarioResponse, 
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(get_admin_user)])


async def create_test_scenario(
    payload: TestScenarioCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new test scenario. Admin-only endpoint."""
    try:
        service = TestScenarioService(db)
        instance = await service.create(payload, current_user.id)
        return instance
    except TestManagementError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": "TEST_002"})


@router.get("/scenarios/{scenario_id}", 
            response_model=TestScenarioResponse,
            dependencies=[Depends(get_admin_user)])


async def get_test_scenario(
    scenario_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get a test scenario by ID. Admin-only endpoint."""
    try:
        service = TestScenarioService(db)
        instance = await service.get_by_id(scenario_id)
        return instance
    except TestManagementError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": str(e), "error_code": "TEST_001"})


@router.put("/scenarios/{scenario_id}", 
            response_model=TestScenarioResponse,
            dependencies=[Depends(get_admin_user)])


async def update_test_scenario(
    scenario_id: int,
    payload: TestScenarioUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Update a test scenario. Admin-only endpoint."""
    try:
        service = TestScenarioService(db)
        instance = await service.update(scenario_id, payload, current_user.id)
        return instance
    except TestManagementError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": "TEST_002"})


@router.delete("/scenarios/{scenario_id}", 
               status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(get_admin_user)])


async def delete_test_scenario(
    scenario_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Delete a test scenario. Admin-only endpoint."""
    try:
        service = TestScenarioService(db)
        await service.delete(scenario_id)
        return
    except TestManagementError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": str(e), "error_code": "TEST_001"})


@router.post("/scenarios/{scenario_id}/execute", 
             response_model=TestExecutionResponse,
             dependencies=[Depends(get_admin_user)])


async def execute_test_scenario(
    scenario_id: int,
    payload: TestExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Execute a test scenario. Admin-only endpoint."""
    try:
        # Verify scenario exists
        scenario_service = TestScenarioService(db)
        await scenario_service.get_by_id(scenario_id)
        
        # Create execution record
        service = TestExecutionService(db)
        instance = await service.create(scenario_id, payload, current_user.id)
        return instance
    except TestManagementError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": "TEST_003"})


@router.get("/executions/{execution_id}", 
            response_model=TestExecutionDetail,
            dependencies=[Depends(get_admin_user)])


async def get_test_execution(
    execution_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get a test execution by ID. Admin-only endpoint."""
    try:
        service = TestExecutionService(db)
        instance = await service.get_by_id(execution_id)
        return instance
    except TestManagementError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": str(e), "error_code": "TEST_004"})


@router.post("/fixtures", 
             response_model=TestFixtureResponse, 
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(get_admin_user)])


async def create_test_fixture(
    payload: TestFixtureCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new test fixture. Admin-only endpoint."""
    try:
        service = TestFixtureService(db)
        instance = await service.create(payload, current_user.id)
        return instance
    except TestManagementError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": "TEST_006"})


@router.get("/fixtures/{fixture_id}/data", 
            response_model=TestFixtureData,
            dependencies=[Depends(get_admin_user)])


async def get_test_fixture_data(
    fixture_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get decrypted test fixture data. Admin-only endpoint."""
    try:
        service = TestFixtureService(db)
        decrypted_data = await service.get_fixture_data(fixture_id)
        return TestFixtureData(id=fixture_id, decrypted_data=decrypted_data)
    except TestManagementError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": str(e), "error_code": "TEST_007"})