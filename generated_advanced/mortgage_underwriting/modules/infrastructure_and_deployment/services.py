from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func as sql_func
import structlog
from mortgage_underwriting.modules.infrastructure_deployment.models import (
    ServiceHealth, 
    DeploymentStatus, 
    ConfigValidation, 
    SystemHealth
)
from mortgage_underwriting.modules.infrastructure_deployment.schemas import (
    ServiceHealthCreate,
    ServiceHealthUpdate,
    ServiceHealthResponse,
    DeploymentStatusCreate,
    DeploymentStatusUpdate,
    DeploymentStatusResponse,
    ConfigValidationCreate,
    ConfigValidationResponse,
    SystemHealthResponse
)
from mortgage_underwriting.modules.infrastructure_deployment.exceptions import (
    ServiceNotFoundError,
    DeploymentStatusNotFoundError,
    SystemHealthNotFoundError
)

logger = structlog.get_logger()


class InfrastructureDeploymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_system_health(self) -> SystemHealthResponse:
        """Get overall system health with aggregated service statuses."""
        logger.info("fetching_system_health")
        
        # Get latest system health record
        stmt = select(SystemHealth).order_by(SystemHealth.timestamp.desc()).limit(1)
        result = await self.db.execute(stmt)
        system_health = result.scalar_one_or_none()
        
        if not system_health:
            logger.warning("no_system_health_records_found")
            raise SystemHealthNotFoundError()
            
        # Get all current service health statuses
        service_stmt = select(ServiceHealth)
        service_result = await self.db.execute(service_stmt)
        services = service_result.scalars().all()
        
        service_dict: Dict[str, Dict[str, Any]] = {}
        for svc in services:
            svc_data = {
                "status": svc.status,
                "response_time_ms": float(svc.response_time_ms) if svc.response_time_ms else None
            }
            if svc.error_message:
                svc_data["error"] = svc.error_message
            if svc.active_workflows is not None:
                svc_data["active_workflows"] = svc.active_workflows
            service_dict[svc.name] = svc_data
        
        return SystemHealthResponse(
            status=system_health.overall_status,
            timestamp=system_health.timestamp,
            version=system_health.version,
            services=service_dict
        )

    async def list_services(self, page: int = 1, size: int = 100) -> Dict[str, Any]:
        """List all registered services with pagination."""
        logger.info("listing_services", page=page, size=size)
        
        offset = (page - 1) * size
        stmt = select(ServiceHealth).offset(offset).limit(size)
        count_stmt = select(sql_func.count(ServiceHealth.id))
        
        result = await self.db.execute(stmt)
        count_result = await self.db.execute(count_stmt)
        
        items = result.scalars().all()
        total = count_result.scalar_one()
        
        return {
            "items": [ServiceHealthResponse.model_validate(item) for item in items],
            "total": total,
            "page": page,
            "size": size
        }

    async def get_service_health(self, service_name: str) -> ServiceHealthResponse:
        """Get detailed health check for a specific service."""
        logger.info("fetching_service_health", service_name=service_name)
        
        stmt = select(ServiceHealth).where(ServiceHealth.name == service_name)
        result = await self.db.execute(stmt)
        service = result.scalar_one_or_none()
        
        if not service:
            logger.warning("service_not_found", service_name=service_name)
            raise ServiceNotFoundError(service_name)
            
        return ServiceHealthResponse.model_validate(service)

    async def validate_config(self, payload: ConfigValidationCreate) -> ConfigValidationResponse:
        """Validate environment configuration (admin-only)."""
        logger.info("validating_configuration", user_id=payload.validator_user_id)
        
        # In a real implementation, this would perform actual validation logic
        # For now, we'll assume it's valid unless there are errors provided
        config_validation = ConfigValidation(**payload.model_dump())
        self.db.add(config_validation)
        await self.db.commit()
        await self.db.refresh(config_validation)
        
        return ConfigValidationResponse.model_validate(config_validation)

    async def get_deployment_status(self) -> DeploymentStatusResponse:
        """Get current deployment version and status (admin-only)."""
        logger.info("fetching_deployment_status")
        
        stmt = select(DeploymentStatus).order_by(DeploymentStatus.deployed_at.desc()).limit(1)
        result = await self.db.execute(stmt)
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            logger.warning("no_deployment_status_records_found")
            raise DeploymentStatusNotFoundError()
            
        return DeploymentStatusResponse.model_validate(deployment)