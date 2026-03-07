from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict

from sqlalchemy import select
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.deployment.models import DeploymentHealthCheck, DependencyHealth
from mortgage_underwriting.modules.deployment.schemas import (
    DeploymentHealthCreate,
    DeploymentHealthResponse,
    DependencyHealthCreate,
    DependencyHealthResponseDetail,
    HealthStatus,
    ComponentHealth,
    DependencyHealthResponse
)

logger = structlog.get_logger()


class DeploymentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_deployment_health_check(self, payload: DeploymentHealthCreate) -> DeploymentHealthResponse:
        """Create a new deployment health check record.

        Args:
            payload: Health check data to store

        Returns:
            Stored health check record
        """
        logger.info("deployment.health_check.create", service_name=payload.service_name)
        
        try:
            instance = DeploymentHealthCheck(
                service_name=payload.service_name,
                status=payload.status.value,
                version=payload.version,
                uptime_seconds=payload.uptime_seconds,
                details=payload.details
            )
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            
            return DeploymentHealthResponse.model_validate(instance)
        except Exception as e:
            await self.db.rollback()
            logger.error("deployment.health_check.create.failed", error=str(e))
            raise AppException(f"Failed to create health check: {str(e)}")

    async def get_deployment_health_history(self, service_name: str, limit: int = 100) -> List[DeploymentHealthResponse]:
        """Retrieve recent health check history for a specific service.

        Args:
            service_name: Name of the service
            limit: Maximum number of records to retrieve (default: 100)

        Returns:
            List of health check records
        """
        logger.info("deployment.health_check.history", service_name=service_name)
        
        try:
            stmt = (
                select(DeploymentHealthCheck)
                .where(DeploymentHealthCheck.service_name == service_name)
                .order_by(DeploymentHealthCheck.created_at.desc())
                .limit(min(limit, 100))
            )
            result = await self.db.execute(stmt)
            instances = result.scalars().all()
            
            return [DeploymentHealthResponse.model_validate(instance) for instance in instances]
        except Exception as e:
            logger.error("deployment.health_check.history.failed", error=str(e))
            raise AppException(f"Failed to retrieve health history: {str(e)}")

    async def create_dependency_health_check(self, payload: DependencyHealthCreate) -> DependencyHealthResponseDetail:
        """Create a new dependency health check record.

        Args:
            payload: Dependency health data to store

        Returns:
            Stored dependency health record
        """
        logger.info("deployment.dependency_health.create", component=payload.component_name)
        
        try:
            instance = DependencyHealth(
                deployment_id=payload.deployment_id,
                component_name=payload.component_name,
                status=payload.status.value,
                latency_ms=payload.latency_ms,
                last_error=payload.last_error
            )
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            
            return DependencyHealthResponseDetail.model_validate(instance)
        except Exception as e:
            await self.db.rollback()
            logger.error("deployment.dependency_health.create.failed", error=str(e))
            raise AppException(f"Failed to create dependency health check: {str(e)}")

    async def get_latest_dependency_health(self, deployment_id: int) -> DependencyHealthResponse:
        """Get latest dependency health status for a deployment.

        Args:
            deployment_id: ID of the deployment health check

        Returns:
            Latest dependency health information
        """
        logger.info("deployment.dependency_health.latest", deployment_id=deployment_id)
        
        try:
            stmt = select(DependencyHealth).where(DependencyHealth.deployment_id == deployment_id)
            result = await self.db.execute(stmt)
            dependencies = result.scalars().all()
            
            # Build response structure
            db_health = ComponentHealth(status="down", latency_ms=None, last_error=None)
            redis_health = ComponentHealth(status="down", latency_ms=None, last_error=None)
            minio_health = ComponentHealth(status="down", latency_ms=None, last_error=None)
            
            overall_status = HealthStatus.HEALTHY
            
            for dep in dependencies:
                if dep.component_name == "database":
                    db_health = ComponentHealth(
                        status=dep.status,
                        latency_ms=dep.latency_ms,
                        last_error=dep.last_error
                    )
                elif dep.component_name == "redis":
                    redis_health = ComponentHealth(
                        status=dep.status,
                        latency_ms=dep.latency_ms,
                        last_error=dep.last_error
                    )
                elif dep.component_name == "minio":
                    minio_health = ComponentHealth(
                        status=dep.status,
                        latency_ms=dep.latency_ms,
                        last_error=dep.last_error
                    )
                
                if dep.status != "up":
                    overall_status = HealthStatus.DEGRADED
            
            return DependencyHealthResponse(
                status=overall_status,
                database=db_health,
                redis=redis_health,
                minio=minio_health
            )
        except Exception as e:
            logger.error("deployment.dependency_health.latest.failed", error=str(e))
            raise AppException(f"Failed to retrieve dependency health: {str(e)}")