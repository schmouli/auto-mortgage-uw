from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import structlog
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.infrastructure.models import ServiceHealth, Deployment, InfrastructureConfig
from mortgage_underwriting.modules.infrastructure.schemas import (
    ServiceHealthCreate,
    ServiceHealthResponse,
    DeploymentCreate,
    DeploymentResponse,
    InfrastructureConfigCreate,
    InfrastructureConfigResponse
)

logger = structlog.get_logger()

class InfrastructureService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_service_health(self, payload: ServiceHealthCreate) -> ServiceHealthResponse:
        logger.info("creating_service_health", service_name=payload.service_name)
        try:
            instance = ServiceHealth(
                service_name=payload.service_name,
                status=payload.status.value,
                version=payload.version,
                details=payload.details
            )
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return ServiceHealthResponse.model_validate(instance)
        except Exception as e:
            await self.db.rollback()
            logger.error("service_health_creation_failed", error=str(e))
            raise AppException(f"Failed to create service health record: {str(e)}")

    async def get_service_health(self, service_name: str) -> Optional[ServiceHealthResponse]:
        logger.info("fetching_service_health", service_name=service_name)
        stmt = select(ServiceHealth).where(ServiceHealth.service_name == service_name).order_by(ServiceHealth.last_check.desc())
        result = await self.db.execute(stmt)
        instance = result.scalars().first()
        if instance:
            return ServiceHealthResponse.model_validate(instance)
        return None

    async def trigger_deployment(self, payload: DeploymentCreate) -> DeploymentResponse:
        logger.info("triggering_deployment", services=payload.services)
        try:
            deployment_id = str(uuid.uuid4())
            services_str = ",".join(payload.services)
            instance = Deployment(
                id=deployment_id,
                services=services_str,
                status="queued",
                triggered_by=payload.triggered_by
            )
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            # Convert comma-separated string back to list
            instance.services = instance.services.split(",") if instance.services else []
            return DeploymentResponse.model_validate(instance)
        except Exception as e:
            await self.db.rollback()
            logger.error("deployment_trigger_failed", error=str(e))
            raise AppException(f"Failed to trigger deployment: {str(e)}")

    async def get_deployment(self, deployment_id: str) -> Optional[DeploymentResponse]:
        logger.info("fetching_deployment", deployment_id=deployment_id)
        stmt = select(Deployment).where(Deployment.id == deployment_id)
        result = await self.db.execute(stmt)
        instance = result.scalars().first()
        if instance:
            # Convert comma-separated string back to list
            instance.services = instance.services.split(",") if instance.services else []
            return DeploymentResponse.model_validate(instance)
        return None

    async def update_deployment_status(self, deployment_id: str, status: str, logs: Optional[str] = None) -> Optional[DeploymentResponse]:
        logger.info("updating_deployment_status", deployment_id=deployment_id, status=status)
        stmt = select(Deployment).where(Deployment.id == deployment_id)
        result = await self.db.execute(stmt)
        instance = result.scalars().first()
        if not instance:
            return None
        
        instance.status = status
        if status in ["success", "failed"]:
            instance.completed_at = datetime.utcnow()
        if logs:
            instance.logs = logs
            
        try:
            await self.db.commit()
            await self.db.refresh(instance)
            # Convert comma-separated string back to list
            instance.services = instance.services.split(",") if instance.services else []
            return DeploymentResponse.model_validate(instance)
        except Exception as e:
            await self.db.rollback()
            logger.error("deployment_update_failed", error=str(e))
            raise AppException(f"Failed to update deployment: {str(e)}")

    async def save_infrastructure_config(self, payload: InfrastructureConfigCreate) -> InfrastructureConfigResponse:
        logger.info("saving_infrastructure_config", service_name=payload.service_name)
        try:
            instance = InfrastructureConfig(
                service_name=payload.service_name,
                config_json=payload.config_json,
                config_hash=payload.config_hash
            )
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return InfrastructureConfigResponse.model_validate(instance)
        except IntegrityError:
            await self.db.rollback()
            logger.warning("config_already_exists", service_name=payload.service_name)
            # Update existing config
            stmt = select(InfrastructureConfig).where(InfrastructureConfig.service_name == payload.service_name)
            result = await self.db.execute(stmt)
            existing = result.scalars().first()
            if existing:
                existing.config_json = payload.config_json
                existing.config_hash = payload.config_hash
                existing.deployed_at = datetime.utcnow()
                await self.db.commit()
                await self.db.refresh(existing)
                return InfrastructureConfigResponse.model_validate(existing)
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error("config_save_failed", error=str(e))
            raise AppException(f"Failed to save infrastructure config: {str(e)}")