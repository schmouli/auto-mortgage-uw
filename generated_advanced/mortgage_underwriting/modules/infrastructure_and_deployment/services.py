from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from sqlalchemy import select
import structlog

from mortgage_underwriting.modules.infrastructure_deployment.models import ServiceHealth, SystemStatus
from mortgage_underwriting.modules.infrastructure_deployment.schemas import (
    ServiceHealthCreate,
    SystemStatusCreate,
    SystemStatusResponse
)

logger = structlog.get_logger()


class InfrastructureDeploymentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_service_health(self, payload: ServiceHealthCreate) -> ServiceHealth:
        # FIXED: Add input validation logging
        logger.info("recording_service_health", service_name=payload.service_name, status=payload.status)
        
        instance = ServiceHealth(
            service_name=payload.service_name,
            status=payload.status,
            details=payload.details
        )
        
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        
        logger.info("service_health_recorded_successfully", service_name=payload.service_name, id=instance.id)
        return instance

    async def record_system_status(self, payload: SystemStatusCreate) -> SystemStatus:
        # FIXED: Add input validation logging
        logger.info("recording_system_status", overall_status=payload.overall_status)
        
        instance = SystemStatus(
            overall_status=payload.overall_status,
            service_statuses=payload.service_statuses,
            gpu_status=payload.gpu_status
        )
        
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        
        logger.info("system_status_recorded_successfully", id=instance.id)
        return instance

    async def get_latest_health(self, service_name: str) -> Optional[ServiceHealth]:
        # FIXED: Add type hint and logging
        logger.debug("fetching_latest_health", service_name=service_name)
        stmt = select(ServiceHealth).where(ServiceHealth.service_name == service_name).order_by(ServiceHealth.checked_at.desc()).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_system_status(self) -> Optional[SystemStatusResponse]:
        # FIXED: Add logging
        logger.debug("fetching_latest_system_status")
        stmt = select(SystemStatus).order_by(SystemStatus.recorded_at.desc()).limit(1)
        result = await self.db.execute(stmt)
        latest = result.scalar_one_or_none()
        
        if latest:
            logger.debug("system_status_found")
            return SystemStatusResponse(
                overall_status=latest.overall_status,
                services=latest.service_statuses,
                gpu_status=latest.gpu_status,
                timestamp=latest.recorded_at
            )
        
        logger.warning("no_system_status_found")
        return None