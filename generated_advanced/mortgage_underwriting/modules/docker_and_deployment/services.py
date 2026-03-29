from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from sqlalchemy import select, func
import structlog
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.docker_deployment.models import Deployment, ServiceHealthCheck
from mortgage_underwriting.modules.docker_deployment.schemas import (
    DeploymentCreate,
    DeploymentResponse,
    ServiceHealthCheckCreate,
    ServiceHealthCheckResponse,
    ServicesHealthOverviewResponse
)

logger = structlog.get_logger()


class DeploymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_deployment(self, payload: DeploymentCreate, user_id: Optional[int] = None) -> DeploymentResponse:
        logger.info("creating_deployment", service=payload.service_name, version=payload.version)
        
        deployment = Deployment(
            service_name=payload.service_name,
            version=payload.version,
            strategy=payload.strategy.value,
            status="pending",
            created_by=user_id
        )
        
        self.db.add(deployment)
        await self.db.commit()
        await self.db.refresh(deployment)
        
        return DeploymentResponse.model_validate(deployment)

    async def get_deployment_status(self, deployment_id: int) -> DeploymentResponse:
        logger.info("fetching_deployment_status", deployment_id=deployment_id)
        
        result = await self.db.execute(select(Deployment).where(Deployment.id == deployment_id))
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            logger.warning("deployment_not_found", deployment_id=deployment_id)
            raise AppException("Deployment not found", "DEPLOYMENT_NOT_FOUND")
            
        return DeploymentResponse.model_validate(deployment)


class HealthCheckService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_health_check(self, payload: ServiceHealthCheckCreate) -> ServiceHealthCheckResponse:
        logger.info("recording_service_health", service=payload.service_name, status=payload.status)
        
        health_check = ServiceHealthCheck(
            service_name=payload.service_name,
            status=payload.status.value,
            latency_ms=payload.latency_ms,
            details=payload.details
        )
        
        self.db.add(health_check)
        await self.db.commit()
        await self.db.refresh(health_check)
        
        return ServiceHealthCheckResponse.model_validate(health_check)

    async def get_services_overview(self) -> ServicesHealthOverviewResponse:
        logger.info("fetching_services_overview")
        
        # Get latest health check per service
        subquery = (
            select(ServiceHealthCheck.service_name, func.max(ServiceHealthCheck.checked_at).label('latest_check'))
            .group_by(ServiceHealthCheck.service_name)
            .subquery()
        )
        
        query = (
            select(ServiceHealthCheck)
            .join(subquery, 
                  (ServiceHealthCheck.service_name == subquery.c.service_name) &
                  (ServiceHealthCheck.checked_at == subquery.c.latest_check))
        )
        
        result = await self.db.execute(query)
        latest_checks = result.scalars().all()
        
        responses = [ServiceHealthCheckResponse.model_validate(check) for check in latest_checks]
        
        # Determine overall system status
        if not responses:
            overall_status = "unknown"
        elif all(c.status == "healthy" for c in responses):
            overall_status = "healthy"
        elif any(c.status == "unhealthy" for c in responses):
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"
        
        return ServicesHealthOverviewResponse(status=overall_status, services=responses)