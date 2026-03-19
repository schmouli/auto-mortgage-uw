from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.migration.schemas import (
    MigrationStatusResponse,
    SeedTriggerRequest,
    SeedTriggerResponse,
    SeedHistoryResponse
)
from mortgage_underwriting.modules.migration.services import MigrationService, SeedDataService

router = APIRouter(prefix="/api/v1/admin/migrations", tags=["Migration Management"])

@router.get("/status", response_model=Dict[str, Any])
async def get_migration_status(
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """Get current migration status including latest revision and pending migrations."""
    service = MigrationService(db)
    current_rev = await service.get_current_revision()
    pending = await service.get_pending_migrations()
    
    return {
        "current_revision": current_rev,
        "pending_migrations": pending
    }

@router.post("/seed/{environment}", response_model=SeedTriggerResponse, status_code=status.HTTP_201_CREATED)
async def trigger_seeding(
    environment: str,
    payload: SeedTriggerRequest,
    db: AsyncSession = Depends(get_async_session),
) -> SeedTriggerResponse:
    """Trigger seed data population for given environment.
    
    Requires explicit confirmation. Truncation allowed only in development.
    """
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Explicit confirmation required", "error_code": "SEED_001"}
        )
        
    if environment not in ["development", "staging", "demo"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": f"Environment '{environment}' not supported", "error_code": "SEED_002"}
        )
        
    if payload.truncate_existing and environment != "development":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Truncation only allowed in development", "error_code": "SEED_003"}
        )
    
    service = SeedDataService(db)
    result = await service.execute_seed(environment, payload.truncate_existing)
    
    return SeedTriggerResponse(
        status="success",
        environment=environment,
        **result
    )