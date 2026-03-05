from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete
from mortgage_underwriting.modules.docker_deployment.models import Deployment, Service, ServiceConfiguration
from mortgage_underwriting.modules.docker_deployment.schemas import (
    DeploymentCreateRequest,
    DeploymentUpdateRequest,
    ServiceCreateRequest,
    ServiceConfigurationCreateRequest
)
from mortgage_underwriting.modules.docker_deployment.exceptions import DeploymentNotFoundError, ServiceNotFoundError, ConfigurationNotFoundError
from mortgage_underwriting.common.security import encrypt_pii
from mortgage_underwriting.common.exceptions import AppException
import structlog

logger = structlog.get_logger()  # FIXED: Using structlog instead of logging


class DeploymentService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
    async def create_deployment(self, deployment_data: DeploymentCreateRequest, changed_by: str) -> Deployment:
        try:
            new_deployment = Deployment(
                name=deployment_data.name,
                description=deployment_data.description,
                environment=deployment_data.environment,
                version=deployment_data.version,
                changed_by=changed_by
            )
            
            self.db.add(new_deployment)
            await self.db.commit()
            await self.db.refresh(new_deployment)
            
            logger.info("deployment_created", deployment_name=new_deployment.name, changed_by=changed_by)
            return new_deployment
            
        except Exception as e:
            await self.db.rollback()
            logger.error("deployment_creation_failed", error=str(e))
            raise AppException("Failed to create deployment") from e
            
    async def get_deployment(self, deployment_id: int) -> Deployment:
        result = await self.db.execute(select(Deployment).where(Deployment.id == deployment_id))
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            logger.warning("deployment_not_found", deployment_id=deployment_id)
            raise DeploymentNotFoundError(f"Deployment with ID {deployment_id} not found")
            
        return deployment
        
    async def list_deployments(self, environment: Optional[str] = None, is_active: Optional[bool] = None) -> List[Deployment]:
        query = select(Deployment)
        
        if environment:
            query = query.where(Deployment.environment == environment)
            
        if is_active is not None:
            query = query.where(Deployment.is_active == is_active)
            
        result = await self.db.execute(query)
        return list(result.scalars().all())
        
    async def update_deployment(self, deployment_id: int, update_data: DeploymentUpdateRequest, changed_by: str) -> Deployment:
        deployment = await self.get_deployment(deployment_id)
        
        if update_data.description is not None:
            deployment.description = update_data.description
            
        if update_data.is_active is not None:
            deployment.is_active = update_data.is_active
            
        deployment.changed_by = changed_by
        
        await self.db.commit()
        await self.db.refresh(deployment)
        
        logger.info("deployment_updated", deployment_id=deployment_id, changed_by=changed_by)
        return deployment
        
    async def delete_deployment(self, deployment_id: int) -> bool:
        deployment = await self.get_deployment(deployment_id)
        await self.db.delete(deployment)
        await self.db.commit()
        
        logger.info("deployment_deleted", deployment_id=deployment_id)
        return True


class ServiceService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
    async def create_service(self, deployment_id: int, service_data: ServiceCreateRequest) -> Service:
        # Verify deployment exists
        deployment_service = DeploymentService(self.db)
        await deployment_service.get_deployment(deployment_id)
        
        new_service = Service(
            deployment_id=deployment_id,
            name=service_data.name,
            image_tag=service_data.image_tag,
            container_port=service_data.container_port,
            replicas=service_data.replicas,
            cpu_limit=service_data.cpu_limit,
            memory_limit_mb=service_data.memory_limit_mb,
            health_check_path=service_data.health_check_path,
            health_check_interval_sec=service_data.health_check_interval_sec,
            health_check_timeout_sec=service_data.health_check_timeout_sec
        )
        
        self.db.add(new_service)
        await self.db.commit()
        await self.db.refresh(new_service)
        
        logger.info("service_created", service_name=new_service.name, deployment_id=deployment_id)
        return new_service
        
    async def get_service(self, service_id: int) -> Service:
        result = await self.db.execute(select(Service).where(Service.id == service_id))
        service = result.scalar_one_or_none()
        
        if not service:
            logger.warning("service_not_found", service_id=service_id)
            raise ServiceNotFoundError(f"Service with ID {service_id} not found")
            
        return service
        
    async def list_services(self, deployment_id: Optional[int] = None, is_active: Optional[bool] = None) -> List[Service]:
        query = select(Service)
        
        if deployment_id:
            query = query.where(Service.deployment_id == deployment_id)
            
        if is_active is not None:
            query = query.where(Service.is_active == is_active)
            
        result = await self.db.execute(query)
        return list(result.scalars().all())
        
    async def update_service(self, service_id: int, service_data: ServiceCreateRequest) -> Service:
        service = await self.get_service(service_id)
        
        service.name = service_data.name
        service.image_tag = service_data.image_tag
        service.container_port = service_data.container_port
        service.replicas = service_data.replicas
        service.cpu_limit = service_data.cpu_limit
        service.memory_limit_mb = service_data.memory_limit_mb
        service.health_check_path = service_data.health_check_path
        service.health_check_interval_sec = service_data.health_check_interval_sec
        service.health_check_timeout_sec = service_data.health_check_timeout_sec
        
        await self.db.commit()
        await self.db.refresh(service)
        
        logger.info("service_updated", service_id=service_id)
        return service
        
    async def delete_service(self, service_id: int) -> bool:
        service = await self.get_service(service_id)
        await self.db.delete(service)
        await self.db.commit()
        
        logger.info("service_deleted", service_id=service_id)
        return True


class ConfigurationService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
    async def create_configuration(self, service_id: int, config_data: ServiceConfigurationCreateRequest) -> ServiceConfiguration:
        # Verify service exists
        service_service = ServiceService(self.db)
        await service_service.get_service(service_id)
        
        config_value = config_data.config_value
        is_encrypted = config_data.is_encrypted
        
        if config_data.is_sensitive:
            config_value = encrypt_pii(config_value)
            is_encrypted = True
            
        new_config = ServiceConfiguration(
            service_id=service_id,
            config_key=config_data.config_key,
            config_value=config_value,
            is_encrypted=is_encrypted,
            is_sensitive=config_data.is_sensitive
        )
        
        self.db.add(new_config)
        await self.db.commit()
        await self.db.refresh(new_config)
        
        logger.info("configuration_created", config_key=new_config.config_key, service_id=service_id)
        return new_config
        
    async def get_configuration(self, config_id: int) -> ServiceConfiguration:
        result = await self.db.execute(select(ServiceConfiguration).where(ServiceConfiguration.id == config_id))
        config = result.scalar_one_or_none()
        
        if not config:
            logger.warning("configuration_not_found", config_id=config_id)
            raise ConfigurationNotFoundError(f"Configuration with ID {config_id} not found")
            
        return config
        
    async def list_configurations(self, service_id: int) -> List[ServiceConfiguration]:
        query = select(ServiceConfiguration).where(ServiceConfiguration.service_id == service_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())
        
    async def delete_configuration(self, config_id: int) -> bool:
        config = await self.get_configuration(config_id)
        await self.db.delete(config)
        await self.db.commit()
        
        logger.info("configuration_deleted", config_id=config_id)
        return True
```

```