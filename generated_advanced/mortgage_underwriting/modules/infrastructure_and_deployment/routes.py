from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query, status, HTTPException
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.infrastructure_deployment.schemas import (
    SystemHealthResponse,
    PaginatedServiceHealthResponse,
    ServiceHealthResponse,
    ConfigValidationCreate,
    ConfigValidationResponse,
    DeploymentStatusResponse
)
from mortgage_underwriting.modules.infrastructure_deployment.services import InfrastructureDeploymentService
from mortgage_underwriting.modules.infrastructure_deployment.exceptions import (
    ServiceNotFoundError,
    DeploymentStatusNotFoundError,
    SystemHealthNotFoundError
)

router = APIRouter(prefix="/api/v1/infrastructure", tags=["Infrastructure & Deployment"])


def get_infra_service(db: AsyncSession = Depends(get_async_session)) -> InfrastructureDeploymentService:
    return InfrastructureDeploymentService(db)


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    service: InfrastructureDeploymentService = Depends(get_infra_service)
) -> SystemHealthResponse:
    """Overall system health aggregate."""
    try:
        return await service.get_system_health()
    except SystemHealthNotFoundError as e:
        raise HTTPException(status_code=404, detail={"detail": str(e), "error_code": "SYSTEM_HEALTH_NOT_FOUND"})


@router.get("/services", response_model=PaginatedServiceHealthResponse)
async def list_services(
    page: int = Query(1, ge=1, le=1000),
    size: int = Query(100, ge=1, le=100),
    service: InfrastructureDeploymentService = Depends(get_infra_service)
) -> PaginatedServiceHealthResponse:
    """List all registered services with status."""
    return await service.list_services(page=page, size=size)


@router.get("/services/{service_name}/health", response_model=ServiceHealthResponse)
async def get_service_health(
    service_name: str,
    service: InfrastructureDeploymentService = Depends(get_infra_service)
) -> ServiceHealthResponse:
    """Detailed health check for specific service."""
    try:
        return await service.get_service_health(service_name)
    except ServiceNotFoundError as e:
        raise HTTPException(status_code=404, detail={"detail": str(e), "error_code": "SERVICE_NOT_FOUND"})


@router.post("/config/validate", response_model=ConfigValidationResponse, status_code=status.HTTP_201_CREATED)
async def validate_config(
    payload: ConfigValidationCreate,
    service: InfrastructureDeploymentService = Depends(get_infra_service)
) -> ConfigValidationResponse:
    """Validate environment configuration (admin-only)."""
    return await service.validate_config(payload)


@router.get("/deployment/status", response_model=DeploymentStatusResponse)
async def get_deployment_status(
    service: InfrastructureDeploymentService = Depends(get_infra_service)
) -> DeploymentStatusResponse:
    """Current deployment version and status (admin-only)."""
    try:
        return await service.get_deployment_status()
    except DeploymentStatusNotFoundError as e:
        raise HTTPException(status_code=404, detail={"detail": str(e), "error_code": "DEPLOYMENT_STATUS_NOT_FOUND"})