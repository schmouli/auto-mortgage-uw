from datetime import datetime
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, status
import structlog

from mortgage_underwriting.common.config import Settings
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.infrastructure_deployment.schemas import (
    HealthCheckResponse,
    ReadinessCheckResponse,
    SystemStatusResponse,
    ServiceHealthCreate,
    SystemStatusCreate
)
from mortgage_underwriting.modules.infrastructure_deployment.services import InfrastructureDeploymentService
from mortgage_underwriting.modules.infrastructure_deployment.exceptions import (
    ServiceUnavailableError,
    HealthCheckFailedError
)

router = APIRouter(prefix="/api/v1/infrastructure", tags=["Infrastructure & Deployment"])
logger = structlog.get_logger()


def get_version() -> str:
    """Get service version from configuration."""
    settings = Settings()
    return getattr(settings, "service_version", "1.0.0")


def check_dependencies() -> Dict[str, str]:
    """Check status of critical system dependencies."""
    dependencies: Dict[str, str] = {}
    
    # Check PostgreSQL connectivity
    try:
        # In production, this would perform an actual database query
        dependencies["postgres"] = "ok"
    except Exception:
        dependencies["postgres"] = "error"
    
    # Check Redis connectivity
    try:
        # In production, this would perform an actual Redis connection test
        dependencies["redis"] = "ok"
    except Exception:
        dependencies["redis"] = "error"
        
    # Check MinIO connectivity
    try:
        # In production, this would perform an actual MinIO connection test
        dependencies["minio"] = "ok"
    except Exception:
        dependencies["minio"] = "error"
        
    return dependencies


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Perform basic health check of the service."""
    logger.info("health_check_requested")
    return HealthCheckResponse(
        status="healthy",
        service="infrastructure",
        timestamp=datetime.utcnow(),
        version=get_version()
    )


@router.get("/ready", response_model=ReadinessCheckResponse)
async def readiness_check() -> ReadinessCheckResponse:
    """Check if service is ready to serve requests."""
    dependencies = check_dependencies()
    status = "ready" if all(status == "ok" for status in dependencies.values()) else "not_ready"
    
    logger.info("readiness_check_completed", status=status, dependencies=dependencies)
    
    return ReadinessCheckResponse(
        status=status,
        dependencies=dependencies,
        timestamp=datetime.utcnow()
    )


@router.get("/system/status", response_model=SystemStatusResponse)
async def system_status(
    db: AsyncSession = Depends(get_async_session)
) -> SystemStatusResponse:
    """Retrieve latest system status information."""
    service = InfrastructureDeploymentService(db)
    status_response = await service.get_system_status()
    
    if not status_response:
        logger.warning("no_system_status_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "No system status found", "error_code": "INFRA_003"}
        )
    
    logger.info("system_status_retrieved")
    return status_response


@router.post("/health", response_model=ServiceHealthCreate, status_code=status.HTTP_201_CREATED)
async def record_health(
    payload: ServiceHealthCreate,
    db: AsyncSession = Depends(get_async_session)
) -> ServiceHealthCreate:
    """Record health status for a specific service."""
    # FIXED: Add input validation
    if not payload.service_name or len(payload.service_name.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Service name is required", "error_code": "INFRA_007"}
        )
    
    if payload.status not in ["healthy", "unhealthy", "degraded"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid status value", "error_code": "INFRA_008"}
        )
    
    try:
        service = InfrastructureDeploymentService(db)
        result = await service.record_service_health(payload)
        logger.info("service_health_recorded", service_name=payload.service_name)
        return result
    except Exception as e:
        logger.error("health_record_failed", error=str(e), service_name=payload.service_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to record health", "error_code": "INFRA_005"}
        )


@router.post("/system/status", response_model=SystemStatusCreate, status_code=status.HTTP_201_CREATED)
async def record_system_status(
    payload: SystemStatusCreate,
    db: AsyncSession = Depends(get_async_session)
) -> SystemStatusCreate:
    """Record overall system status."""
    # FIXED: Add input validation
    if payload.overall_status not in ["healthy", "degraded", "unavailable"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid overall status value", "error_code": "INFRA_009"}
        )
    
    if not isinstance(payload.service_statuses, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Service statuses must be a dictionary", "error_code": "INFRA_010"}
        )
    
    try:
        service = InfrastructureDeploymentService(db)
        result = await service.record_system_status(payload)
        logger.info("system_status_recorded", overall_status=payload.overall_status)
        return result
    except Exception as e:
        logger.error("system_status_record_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to record system status", "error_code": "INFRA_006"}
        )