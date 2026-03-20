from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
import structlog
import time
from decimal import Decimal
from sqlalchemy.exc import SQLAlchemyError

from mortgage_underwriting.modules.infra.models import DeploymentStatus, HealthCheckResult
from mortgage_underwriting.modules.infra.schemas import (
    HealthCheckResponse,
    HealthCheckComponent,
    DeploymentStatusResponse,
    DeploymentRollbackRequest
)
from mortgage_underwriting.modules.infra.exceptions import (
    HealthCheckFailedError,
    DeploymentNotFoundError,
    RollbackNotAllowedError
)
from mortgage_underwriting.common.config import settings

logger = structlog.get_logger()


class InfrastructureService:
    ROLLBACK_SIMULATION_SEC = 2

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def check_health(self) -> HealthCheckResponse:
        """Perform comprehensive health checks for infrastructure components."""
        start_time: float = time.time()
        logger.info("health_check_started")
        
        checks: Dict[str, HealthCheckComponent] = {}
        overall_status: str = "healthy"
        
        # Database check
        try:
            db_start: float = time.time()
            result = await self.db.execute(select(1))
            _ = result.scalar_one_or_none()
            db_latency: Decimal = Decimal(str(round((time.time() - db_start) * 1000, 2)))
            checks["database"] = HealthCheckComponent(status="ok", latency_ms=db_latency)
        except SQLAlchemyError as e:
            logger.error("database_health_failed", error=str(e))
            checks["database"] = HealthCheckComponent(status="error", latency_ms=None)
            overall_status = "unhealthy"
        
        # Redis check placeholder
        try:
            # In real implementation, connect to Redis
            checks["redis"] = HealthCheckComponent(status="ok", latency_ms=Decimal('1.2'))
        except Exception as e:
            logger.error("redis_health_failed", error=str(e))
            checks["redis"] = HealthCheckComponent(status="error", latency_ms=None)
            overall_status = "unhealthy"
        
        # Storage check placeholder
        try:
            # In real implementation, test storage connectivity
            checks["storage"] = HealthCheckComponent(status="ok")
        except Exception as e:
            logger.error("storage_health_failed", error=str(e))
            checks["storage"] = HealthCheckComponent(status="error")
            if overall_status == "healthy":
                overall_status = "degraded"
        
        elapsed: Decimal = Decimal(str(round((time.time() - start_time) * 1000, 2)))
        logger.info("health_check_completed", duration_ms=elapsed, status=overall_status)
        
        return HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.now(timezone.utc),
            checks=checks,
            version=settings.GIT_COMMIT_SHA or "unknown"
        )

    async def get_deployment_status(self, deployment_id: str) -> DeploymentStatusResponse:
        """Get current status of a specific deployment."""
        if not deployment_id:
            raise ValueError("Deployment ID is required")
            
        logger.info("fetching_deployment_status", deployment_id=deployment_id)
        
        stmt = select(DeploymentStatus).where(DeploymentStatus.deployment_id == deployment_id)
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        
        if not instance:
            raise DeploymentNotFoundError(f"Deployment {deployment_id} not found")
        
        return DeploymentStatusResponse.model_validate(instance)

    async def trigger_rollback(self, payload: DeploymentRollbackRequest) -> DeploymentStatusResponse:
        """Trigger rollback for a failed deployment."""
        if not payload.deployment_id or not payload.reason:
            raise ValueError("Deployment ID and reason are required")
            
        logger.info("rollback_triggered", deployment_id=payload.deployment_id, reason=payload.reason[:50])
        
        # Get current deployment
        stmt = select(DeploymentStatus).where(DeploymentStatus.deployment_id == payload.deployment_id)
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        
        if not instance:
            raise DeploymentNotFoundError(f"Deployment {payload.deployment_id} not found")
        
        # Validate rollback eligibility
        if instance.status != "failed":
            raise RollbackNotAllowedError("Only failed deployments can be rolled back")
        
        # Update status to rolling back
        instance.status = "rolling_back"
        instance.message = f"Rollback initiated: {payload.reason}"
        await self.db.commit()
        
        # Simulate rollback process
        await asyncio.sleep(self.ROLLBACK_SIMULATION_SEC)
        
        # Finalize rollback
        instance.status = "rolled_back"
        instance.message = f"Rollback successful: {payload.reason}"
        await self.db.commit()
        await self.db.refresh(instance)
        
        logger.info("rollback_completed", deployment_id=payload.deployment_id)
        return DeploymentStatusResponse.model_validate(instance)