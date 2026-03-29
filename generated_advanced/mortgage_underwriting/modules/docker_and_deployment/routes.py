from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.docker_deployment.schemas import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentStatusResponse,
    ServiceHealthCheckCreate,
    ServiceHealthCheckResponse,
    ServicesHealthOverviewResponse
)
from mortgage_underwriting.modules.docker_deployment.services import DeploymentService, HealthCheckService

router = APIRouter(prefix="/api/v1/deployments", tags=["Docker & Deployment"])


@router.post("/", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    request: Request,
    payload: DeploymentCreate,
    db: AsyncSession = Depends(get_async_session),
) -> DeploymentResponse:
    """Create a new deployment."""
    service = DeploymentService(db)
    user_id = getattr(request.state, 'user_id', None)
    return await service.create_deployment(payload, user_id)


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment_status(
    deployment_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> DeploymentResponse:
    """Get deployment status by ID."""
    if deployment_id <= 0:
        raise HTTPException(status_code=400, detail={"detail": "Invalid deployment ID", "error_code": "INVALID_DEPLOYMENT_ID"})
    service = DeploymentService(db)
    return await service.get_deployment_status(deployment_id)


@router.post("/health-checks", response_model=ServiceHealthCheckResponse, status_code=status.HTTP_201_CREATED)
async def record_health_check(
    payload: ServiceHealthCheckCreate,
    db: AsyncSession = Depends(get_async_session),
) -> ServiceHealthCheckResponse:
    """Record a service health check."""
    service = HealthCheckService(db)
    return await service.record_health_check(payload)


@router.get("/health/services", response_model=ServicesHealthOverviewResponse)
async def get_services_overview(
    db: AsyncSession = Depends(get_async_session),
) -> ServicesHealthOverviewResponse:
    """Get overview of all service health statuses."""
    service = HealthCheckService(db)
    return await service.get_services_overview()