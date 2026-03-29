from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.migrations.schemas import (
    MigrationRecordCreate,
    MigrationRecordUpdate,
    MigrationRecordResponse,
)
from mortgage_underwriting.modules.migrations.services import MigrationService

router = APIRouter(prefix="/api/v1/migrations", tags=["Database Migrations"])


@router.post("/", response_model=MigrationRecordResponse, status_code=status.HTTP_201_CREATED)
async def record_migration(
    payload: MigrationRecordCreate,
    db: AsyncSession = Depends(get_async_session),
) -> MigrationRecordResponse:
    service = MigrationService(db)
    try:
        return await service.record_migration(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "MIGRATION_RECORD_FAILED"},
        ) from e


@router.patch("/{version}", response_model=MigrationRecordResponse)
async def update_migration_status(
    version: str,
    payload: MigrationRecordUpdate,
    db: AsyncSession = Depends(get_async_session),
) -> MigrationRecordResponse:
    service = MigrationService(db)
    result = await service.update_migration_status(version, payload)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": f"Migration {version} not found",
                "error_code": "MIGRATION_NOT_FOUND",
            },
        )
    return result


@router.get("/", response_model=List[MigrationRecordResponse])
async def list_migrations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: AsyncSession = Depends(get_async_session),
) -> List[MigrationRecordResponse]:
    service = MigrationService(db)
    return await service.get_all_migrations()