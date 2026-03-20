from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.infra.schemas import (
    HealthCheckResponse,
    DeploymentStatusResponse,
    DeploymentRollbackRequest,
    SimpleMessageResponse
)
from mortgage_underwriting.modules.infra.services import InfrastructureService
from mortgage_underwriting.modules.infra.exceptions import (
    DeploymentNotFoundError,
    RollbackNotAllowedError
)

router = APIRouter(prefix="/api/v1/infra", tags=["Infrastructure & Deployment"])


@router.get("/health/live", response_model=SimpleMessageResponse, status_code=status.HTTP_200_OK)
async def liveness_probe() -> SimpleMessageResponse:
    """Liveness probe endpoint - returns immediately if service is running."""
    return SimpleMessageResponse(detail="OK")


@router.get("/health/ready", response_model=HealthCheckResponse, status_code=status.HTTP_200_OK)
async def readiness_probe(
    db: AsyncSession = Depends(get_async_session)
) -> HealthCheckResponse:
    """Readiness probe endpoint - checks dependencies are ready."""
    service = InfrastructureService(db)
    try:
        return await service.check_health()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"detail": str(e), "error_code": "INFRA_001"}
        )


@router.get("/deployment/status/{deployment_id}", response_model=DeploymentStatusResponse)
async def get_deployment_status(
    deployment_id: str,
    db: AsyncSession = Depends(get_async_session)
) -> DeploymentStatusResponse:
    """Fetch detailed status of a deployment by ID."""
    service = InfrastructureService(db)
    try:
        return await service.get_deployment_status(deployment_id)
    except DeploymentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "DEPLOYMENT_NOT_FOUND"}
        )


@router.post("/deployment/rollback", response_model=DeploymentStatusResponse)
async def trigger_rollback(
    payload: DeploymentRollbackRequest,
    db: AsyncSession = Depends(get_async_session)
) -> DeploymentStatusResponse:
    """Initiate rollback for a failed deployment."""
    service = InfrastructureService(db)
    try:
        return await service.trigger_rollback(payload)
    except DeploymentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "DEPLOYMENT_NOT_FOUND"}
        )
    except RollbackNotAllowedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "ROLLBACK_NOT_ALLOWED"}
        )


@router.get("/donut/health", response_model=SimpleMessageResponse)
async def donut_health_check() -> SimpleMessageResponse:
    """GPU/ML model health check for DPT service."""
    # Placeholder for actual GPU/model checks
    return SimpleMessageResponse(detail="Donut model is healthy")


@router.get("/metrics")
async def prometheus_metrics() -> str:
    """Prometheus metrics endpoint (stub)."""
    return "# Metrics endpoint stub\n"