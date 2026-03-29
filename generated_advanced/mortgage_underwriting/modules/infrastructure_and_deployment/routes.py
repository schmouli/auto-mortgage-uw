from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status
import structlog
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.infrastructure.schemas import (
    ServiceHealthCreate,
    ServiceHealthResponse,
    DeploymentCreate,
    DeploymentResponse,
    InfrastructureConfigCreate,
    InfrastructureConfigResponse,
    HealthCheckResponse,
    ReadinessCheckResponse
)
from mortgage_underwriting.modules.infrastructure.services import InfrastructureService

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/infrastructure", tags=["Infrastructure"])

@router.get("/health", response_model=HealthCheckResponse, status_code=status.HTTP_200_OK)
async def health_check():
    """Liveness probe endpoint."""
    logger.info("health_check_requested")
    return HealthCheckResponse(
        status="healthy",
        service="infrastructure",
        timestamp=datetime.utcnow()
    )

@router.get("/ready", response_model=ReadinessCheckResponse, status_code=status.HTTP_200_OK)
async def readiness_check():
    """Readiness probe endpoint."""
    logger.info("readiness_check_requested")
    # In a real implementation, check dependencies like DB, Redis, etc.
    return ReadinessCheckResponse(
        status="ready",
        checks={"db": "ok", "redis": "ok"},
        version="v1.0.0"
    )

@router.get("/health/{service_name}", response_model=ServiceHealthResponse)
async def get_service_health_endpoint(
    service_name: str,
    db: AsyncSession = Depends(get_async_session)
) -> ServiceHealthResponse:
    """Get the latest health status for a specific service."""
    service = InfrastructureService(db)
    health = await service.get_service_health(service_name)
    if not health:
        raise HTTPException(status_code=404, detail="Service health not found")
    return health

@router.post("/health", response_model=ServiceHealthResponse, status_code=status.HTTP_201_CREATED)
async def create_service_health_endpoint(
    payload: ServiceHealthCreate,
    db: AsyncSession = Depends(get_async_session)
) -> ServiceHealthResponse:
    """Record a new service health status."""
    service = InfrastructureService(db)
    try:
        return await service.create_service_health(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/deployments", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def trigger_deployment_endpoint(
    payload: DeploymentCreate,
    db: AsyncSession = Depends(get_async_session)
) -> DeploymentResponse:
    """Trigger a new deployment."""
    service = InfrastructureService(db)
    try:
        return await service.trigger_deployment(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/deployments/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment_endpoint(
    deployment_id: str,
    db: AsyncSession = Depends(get_async_session)
) -> DeploymentResponse:
    """Get deployment status by ID."""
    service = InfrastructureService(db)
    deployment = await service.get_deployment(deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deployment

@router.post("/configs", response_model=InfrastructureConfigResponse, status_code=status.HTTP_201_CREATED)
async def save_infrastructure_config_endpoint(
    payload: InfrastructureConfigCreate,
    db: AsyncSession = Depends(get_async_session)
) -> InfrastructureConfigResponse:
    """Save or update infrastructure configuration."""
    service = InfrastructureService(db)
    try:
        return await service.save_infrastructure_config(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))