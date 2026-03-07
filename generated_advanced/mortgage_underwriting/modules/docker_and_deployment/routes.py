from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.deployment.schemas import (
    HealthResponse,
    DependencyHealthResponse,
    DeploymentHealthCreate,
    DeploymentHealthResponse,
    DependencyHealthCreate,
    DependencyHealthResponseDetail
)
from mortgage_underwriting.modules.deployment.services import DeploymentService

router = APIRouter(prefix="/api/v1/deployment", tags=["Deployment"])

@router.get("/health", response_model=HealthResponse)
async def get_backend_health(
    db: AsyncSession = Depends(get_async_session)
) -> HealthResponse:
    """Get backend service health status."""
    # In real implementation, would perform actual health checks
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        uptime_seconds=3600,
        checks={"db": True, "redis": True, "minio": True},
        timestamp=datetime.utcnow()
    )

@router.get("/health/dependencies", response_model=DependencyHealthResponse)
async def get_dependencies_health(
    db: AsyncSession = Depends(get_async_session)
) -> DependencyHealthResponse:
    """Get backend service dependencies health status."""
    # In real implementation, would perform actual dependency checks
    return DependencyHealthResponse(
        status="healthy",
        database={"status": "up", "latency_ms": 5.2, "last_error": None},
        redis={"status": "up", "latency_ms": 1.1, "last_error": None},
        minio={"status": "up", "latency_ms": 12.3, "last_error": None}
    )

@router.post("/health-checks", 
             response_model=DeploymentHealthResponse,
             status_code=status.HTTP_201_CREATED)
async def create_deployment_health_check(
    payload: DeploymentHealthCreate,
    db: AsyncSession = Depends(get_async_session)
) -> DeploymentHealthResponse:
    """Create a new deployment health check record."""
    service = DeploymentService(db)
    try:
        return await service.create_deployment_health_check(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DEPLOYMENT_001"}
        )

@router.get("/health-checks/{service_name}", 
            response_model=List[DeploymentHealthResponse])
async def get_deployment_health_history(
    service_name: str,
    limit: int = Query(100, le=100),
    db: AsyncSession = Depends(get_async_session)
) -> List[DeploymentHealthResponse]:
    """Get deployment health check history for a service."""
    service = DeploymentService(db)
    try:
        return await service.get_deployment_health_history(service_name, limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DEPLOYMENT_002"}
        )

@router.post("/dependency-health", 
             response_model=DependencyHealthResponseDetail,
             status_code=status.HTTP_201_CREATED)
async def create_dependency_health_check(
    payload: DependencyHealthCreate,
    db: AsyncSession = Depends(get_async_session)
) -> DependencyHealthResponseDetail:
    """Create a new dependency health check record."""
    service = DeploymentService(db)
    try:
        return await service.create_dependency_health_check(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "DEPLOYMENT_003"}
        )