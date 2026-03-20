from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.database.schemas import (
    MigrationApplyRequest,
    MigrationStatusResponse,
    MigrationApplyResponse,
    SeedRequest,
    SeedResponse,
    RollbackTestRequest,
    RollbackTestResponse
)
from mortgage_underwriting.modules.database.services import DatabaseMigrationService, SeedDataService

router = APIRouter(prefix="/api/v1/admin/database", tags=["Database Management"])

@router.post("/migrate/up", response_model=MigrationApplyResponse, status_code=status.HTTP_200_OK)
async def migrate_up(
    payload: MigrationApplyRequest,
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Run database migrations forward."""
    service = DatabaseMigrationService(db)
    return await service.migrate_up(payload.revision)

@router.post("/migrate/down", response_model=MigrationApplyResponse, status_code=status.HTTP_200_OK)
async def migrate_down(
    payload: MigrationApplyRequest,
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Run database migrations backward."""
    service = DatabaseMigrationService(db)
    return await service.migrate_down(payload.revision)

@router.get("/migrate/status", response_model=MigrationStatusResponse, status_code=status.HTTP_200_OK)
async def get_migration_status(
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Get current migration status."""
    service = DatabaseMigrationService(db)
    return await service.get_status()

@router.post("/seed/{environment}", response_model=SeedResponse, status_code=status.HTTP_200_OK)
async def seed_data(
    environment: str,
    payload: SeedRequest,
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Seed database with initial data."""
    service = SeedDataService(db)
    return await service.seed_environment(environment, payload.confirm, payload.truncate_first)

@router.post("/seed/rollback-test", response_model=RollbackTestResponse, status_code=status.HTTP_200_OK)
async def test_rollback(
    payload: RollbackTestRequest,
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Test rollback functionality."""
    service = SeedDataService(db)
    return await service.test_rollback(payload.test_scenario)