from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.config import settings
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.testing.schemas import (
    TestScenarioCreate,
    TestScenarioResponse,
    TestDataSeedRequest,
    TestDataSeedResponse,
    TestDataCleanupRequest,
    TestDataCleanupResponse
)
from mortgage_underwriting.modules.testing.services import TestScenarioService, TestDataService

router = APIRouter(prefix="/api/v1/test-only", tags=["Testing Utilities"])

# These endpoints should be disabled in production via middleware or config check

@router.post("/scenarios", response_model=TestScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_test_scenario(
    payload: TestScenarioCreate,
    db: AsyncSession = Depends(get_async_session),
    x_api_key: Optional[str] = Header(None)
) -> TestScenarioResponse:
    """Create a new test scenario definition."""
    if not settings.ENABLE_TEST_ENDPOINTS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"detail": "Test endpoints disabled in production", "error_code": "TEST_001"})
    if x_api_key != settings.TEST_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"detail": "Invalid test API key", "error_code": "TEST_004"})
        
    service = TestScenarioService(db)
    return await service.create(payload)


@router.post("/seed-data", response_model=TestDataSeedResponse, status_code=status.HTTP_201_CREATED)
async def seed_test_data(
    payload: TestDataSeedRequest,
    db: AsyncSession = Depends(get_async_session),
    x_api_key: Optional[str] = Header(None)
) -> TestDataSeedResponse:
    """Seed synthetic test data based on a predefined scenario."""
    if not settings.ENABLE_TEST_ENDPOINTS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"detail": "Test endpoints disabled in production", "error_code": "TEST_001"})
    if x_api_key != settings.TEST_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"detail": "Invalid test API key", "error_code": "TEST_004"})
        
    service = TestDataService(db)
    return await service.seed_data(payload, None)  # In real app, extract user ID from auth


@router.delete("/cleanup", response_model=TestDataCleanupResponse)
async def cleanup_test_data(
    payload: TestDataCleanupRequest,
    db: AsyncSession = Depends(get_async_session),
    x_api_key: Optional[str] = Header(None)
) -> TestDataCleanupResponse:
    """Clean up previously seeded test data using the provided token."""
    if not settings.ENABLE_TEST_ENDPOINTS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"detail": "Test endpoints disabled in production", "error_code": "TEST_001"})
    if x_api_key != settings.TEST_API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"detail": "Invalid test API key", "error_code": "TEST_004"})
        
    service = TestDataService(db)
    return await service.cleanup_data(payload, None)  # In real app, extract user ID from auth