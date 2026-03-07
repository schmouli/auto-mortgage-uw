from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import Dict, Any
import structlog
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.migrations.schemas import (
    MigrationStatusResponse, 
    SeedExecutionRequest, 
    SeedExecutionResponse
)
from mortgage_underwriting.modules.migrations.services import MigrationService
from mortgage_underwriting.modules.migrations.exceptions import MigrationException

router = APIRouter(prefix="/api/v1/system", tags=["System"])
logger = structlog.get_logger()

# Hardcoded token for demo purposes - in reality should come from secure config
SEED_AUTH_TOKEN = "SEED_EXECUTION_TOKEN_PLACEHOLDER"

@router.get("/migration-status", response_model=MigrationStatusResponse)
async def get_migration_status(
    db: AsyncSession = Depends(get_async_session),
    x_admin_token: str = Header(..., description="Admin authorization token")
) -> Dict[str, Any]:
    """Get current migration status."""
    # In real app, validate admin token here
    if x_admin_token != "VALID_ADMIN_TOKEN":
        logger.warning("unauthorized_access_attempt", endpoint="/migration-status")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail={"detail": "Admin access required", "error_code": "AUTH_002"}
        )
        
    service = MigrationService(db)
    try:
        status_info = await service.get_migration_status()
        return status_info
    except MigrationException as e:
        logger.error("migration_status_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail={"detail": "Migration system unavailable", "error_code": "SYSTEM_001"}
        )

@router.post("/seed", response_model=SeedExecutionResponse)
async def execute_seed(
    payload: SeedExecutionRequest,
    db: AsyncSession = Depends(get_async_session),
    authorization: str = Header(..., description="Seed execution authorization")
) -> Dict[str, Any]:
    """Execute seed data population (admin only)."""
    if authorization != SEED_AUTH_TOKEN:
        logger.warning("unauthorized_seed_execution_attempt")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail={"detail": "Unauthorized seed execution", "error_code": "AUTH_003"}
        )
    
    service = MigrationService(db)
    try:
        result = await service.execute_seed(
            env=payload.environment,
            dry_run=payload.dry_run,
            force=payload.force,
            scenario=payload.scenario
        )
        return result
    except MigrationException as e:
        logger.error("seed_execution_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail={"detail": "Seed execution failed", "error_code": "SYSTEM_002"}
        )