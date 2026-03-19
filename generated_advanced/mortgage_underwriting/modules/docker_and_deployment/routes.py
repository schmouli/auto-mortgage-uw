from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import ValidationError
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.deployment.schemas import (
    ServiceHealthCreate,
    ServiceHealthResponse,
    DeploymentLogCreate,
    DeploymentLogResponse,
    HealthCheckResponse,
    RestartServiceRequest
)
from mortgage_underwriting.modules.deployment.services import DeploymentService

router = APIRouter(prefix="/api/v1/deployment", tags=["Deployment"])

@router.get("/health", response_model=HealthCheckResponse)
async def get_health_status(
    db: AsyncSession = Depends(get_async_session),
) -> HealthCheckResponse:
    """Get overall system health status."""
    service = DeploymentService(db)
    return await service.get_system_health()

@router.post("/services/health", response_model=ServiceHealthResponse, status_code=status.HTTP_201_CREATED)
async def record_service_health(
    payload: ServiceHealthCreate,
    db: AsyncSession = Depends(get_async_session),
) -> ServiceHealthResponse:
    """Record health status for a specific service."""
    # Validate payload
    try:
        payload.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"detail": f"Invalid input: {e}", "error_code": "VALIDATION_ERROR"})
    
    service = DeploymentService(db)
    return await service.record_service_health(payload)

@router.post("/services/{service_name}/restart", 
             response_model=Dict[str, str], 
             status_code=status.HTTP_202_ACCEPTED)
async def restart_service(
    service_name: str,
    payload: RestartServiceRequest,
    db: AsyncSession = Depends(get_async_session),
) -> Dict[str, str]:
    """Initiate restart of a specific service."""
    # Validate service name format
    if not service_name or len(service_name) > 100:
        raise HTTPException(status_code=400, detail={"detail": "Invalid service name", "error_code": "INVALID_SERVICE_NAME"})
    
    service = DeploymentService(db)
    return await service.restart_service(service_name, payload.force)

@router.post("/logs", response_model=DeploymentLogResponse, status_code=status.HTTP_201_CREATED)
async def log_deployment(
    payload: DeploymentLogCreate,
    db: AsyncSession = Depends(get_async_session),
) -> DeploymentLogResponse:
    """Log a deployment event."""
    # Validate payload
    try:
        payload.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"detail": f"Invalid input: {e}", "error_code": "VALIDATION_ERROR"})
    
    service = DeploymentService(db)
    return await service.log_deployment(payload)