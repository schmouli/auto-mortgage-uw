from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional
from sqlalchemy import select, func
import structlog
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.deployment.models import ServiceHealth, DeploymentLog
from mortgage_underwriting.modules.deployment.schemas import (
    ServiceHealthCreate,
    ServiceHealthResponse,
    DeploymentLogCreate,
    DeploymentLogResponse,
    HealthCheckResponse,
    ServiceStatus,
    DeploymentStatus
)

logger = structlog.get_logger()

class DeploymentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_service_health(self, payload: ServiceHealthCreate) -> ServiceHealthResponse:
        """Record service health status."""
        logger.info("recording_service_health", service_name=payload.service_name)
        try:
            instance = ServiceHealth(**payload.model_dump())
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return ServiceHealthResponse.model_validate(instance)
        except Exception as e:
            await self.db.rollback()
            logger.error("service_health_record_failed", error=str(e))
            raise AppException(f"Failed to record service health: {str(e)}")

    async def get_system_health(self) -> HealthCheckResponse:
        """Get overall system health status."""
        logger.info("fetching_system_health")
        try:
            # Get latest health status for each service
            subq = (
                select(
                    ServiceHealth.service_name,
                    func.max(ServiceHealth.timestamp).label('latest_timestamp')
                )
                .group_by(ServiceHealth.service_name)
                .subquery()
            )
            
            stmt = (
                select(ServiceHealth)
                .join(subq, 
                      (ServiceHealth.service_name == subq.c.service_name) &
                      (ServiceHealth.timestamp == subq.c.latest_timestamp))
            )
            
            result = await self.db.execute(stmt)
            services: List[ServiceHealth] = result.scalars().all()
            
            # Determine overall system status
            overall_status = ServiceStatus.HEALTHY
            for service in services:
                if service.status == ServiceStatus.UNHEALTHY:
                    overall_status = ServiceStatus.UNHEALTHY
                    break
                elif service.status == ServiceStatus.DEGRADED and overall_status == ServiceStatus.HEALTHY:
                    overall_status = ServiceStatus.DEGRADED
            
            services_dict = {
                s.service_name: ServiceHealthResponse.model_validate(s) 
                for s in services
            }
            
            return HealthCheckResponse(
                status=overall_status,
                timestamp=datetime.utcnow(),
                services=services_dict
            )
        except Exception as e:
            logger.error("system_health_fetch_failed", error=str(e))
            raise AppException(f"Failed to fetch system health: {str(e)}")

    async def log_deployment(self, payload: DeploymentLogCreate) -> DeploymentLogResponse:
        """Log a deployment event."""
        logger.info("logging_deployment", service_name=payload.service_name, version=payload.version)
        try:
            instance = DeploymentLog(**payload.model_dump())
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return DeploymentLogResponse.model_validate(instance)
        except Exception as e:
            await self.db.rollback()
            logger.error("deployment_log_failed", error=str(e))
            raise AppException(f"Failed to log deployment: {str(e)}")

    async def restart_service(self, service_name: str, force: bool = False) -> Dict[str, str]:
        """Initiate service restart."""
        logger.info("initiating_service_restart", service_name=service_name, force=force)
        # In a real implementation, this would integrate with container orchestration
        # For now, we'll just log the intent
        try:
            # Record the restart attempt
            deployment_log = DeploymentLogCreate(
                service_name=service_name,
                version="restart-initiated",
                status=DeploymentStatus.DEPLOYING,
                initiated_by=None,  # Would come from auth context
                error_details=f"Restart initiated with force={force}"
            )
            await self.log_deployment(deployment_log)
            
            return {"status": "restart_initiated", "service": service_name}
        except Exception as e:
            logger.error("service_restart_failed", service_name=service_name, error=str(e))
            raise AppException(f"Failed to restart service {service_name}: {str(e)}")