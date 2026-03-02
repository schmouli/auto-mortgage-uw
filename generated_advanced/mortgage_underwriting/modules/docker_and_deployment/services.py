```python
from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete
from .models import Deployment, Service, ServiceConfiguration
from .schemas import (
    DeploymentCreateRequest,
    DeploymentUpdateRequest,
    ServiceCreateRequest,
    ServiceConfigurationCreateRequest
)
from .exceptions import DeploymentNotFoundError, ServiceNotFoundError, ConfigurationNotFoundError
from common.security.encryption import encrypt_data, decrypt_data
from common.exceptions import DatabaseError
import logging


logger = logging.getLogger(__name__)


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
            
            logger.info(f"Created deployment {new_deployment.name} by {changed_by}")
            return new_deployment
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create deployment: {str(e)}")
            raise DatabaseError("Failed to create deployment") from e
            
    async def get_deployment(self, deployment_id: int) -> Deployment:
        result = await self.db.execute(select(Deployment).where(Deployment.id == deployment_id))
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            raise DeploymentNotFoundError(deployment_id)
            
        return deployment
        
    async def update_deployment(
        self, 
        deployment_id: int, 
        update_data: DeploymentUpdateRequest, 
        changed_by: str
    ) -> Deployment:
        deployment = await self.get_deployment(deployment_id)
        
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(deployment, field, value)
            
        deployment.changed_by = changed_by
        
        await self.db.commit()
        await self.db.refresh(deployment)
        
        logger.info(f"Updated deployment {deployment_id} by {changed_by}")
        return deployment
        
    async def list_deployments(self, environment: Optional[str] = None) -> List[Deployment]:
        query = select(Deployment)
        if environment:
            query = query.where(Deployment.environment == environment)
            
        result = await self.db.execute(query)
        return result.scalars().all()
        
    async def delete_deployment(self, deployment_id: int) -> bool:
        deployment = await self.get_deployment(deployment_id)
        
        # Delete associated services first
        await self.db.execute(delete(Service).where(Service.deployment_id == deployment_id))
        
        await self.db.delete(deployment)
        await self.db.commit()
        
        logger.info(f"Deleted deployment {deployment_id}")
        return True


class ServiceService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
    async def create_service(
        self, 
        deployment_id: int, 
        service_data: ServiceCreateRequest, 
        changed_by: str
    ) -> Service:
        try:
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
                health_check_timeout_sec=service_data.health_check_timeout_sec,
                changed_by=changed_by
            )
            
            self.db.add(new_service)
            await self.db.commit()
            await self.db.refresh(new_service)
            
            logger.info(f"Created service {new_service.name} for deployment {deployment_id} by {changed_by}")
            return new_service
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create service: {str(e)}")
            raise DatabaseError("Failed to create service") from e
            
    async def get_service(self, service_id: int) -> Service:
        result = await self.db.execute(select(Service).where(Service.id == service_id))
        service = result.scalar_one_or_none()
        
        if not service:
            raise ServiceNotFoundError(service_id)
            
        return service
        
    async def update_service(
        self, 
        service_id: int, 
        update_data: ServiceCreateRequest, 
        changed_by: str
    ) -> Service:
        service = await self.get_service(service_id)
        
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(service, field, value)
            
        service.changed_by = changed_by
        
        await self.db.commit()
        await self.db.refresh(service)
        
        logger.info(f"Updated service {service_id} by {changed_by}")
        return service
        
    async def list_services(self, deployment_id: Optional[int] = None) -> List[Service]:
        query = select(Service)
        if deployment_id:
            query = query.where(Service.deployment_id == deployment_id)
            
        result = await self.db.execute(query)
        return result.scalars().all()
        
    async def delete_service(self, service_id: int) -> bool:
        service = await self.get_service(service_id)
        
        # Delete associated configurations first
        await self.db.execute(
            delete(ServiceConfiguration).where(ServiceConfiguration.service_id == service_id)
        )
        
        await self.db.delete(service)
        await self.db.commit()
        
        logger.info(f"Deleted service {service_id}")
        return True


class ConfigurationService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
    async def create_configuration(
        self, 
        service_id: int, 
        config_data: ServiceConfigurationCreateRequest, 
        changed_by: str
    ) -> ServiceConfiguration:
        try:
            # Encrypt value if needed
            config_value = config_data.config_value
            if config_data.is_encrypted:
                config_value = encrypt_data(config_value)
                
            new_config = ServiceConfiguration(
                service_id=service_id,
                config_key=config_data.config_key,
                config_value=config_value,
                is_encrypted=config_data.is_encrypted,
                changed_by=changed_by
            )
            
            self.db.add(new_config)
            await self.db.commit()
            await self.db.refresh(new_config)
            
            logger.info(f"Created configuration {new_config.config_key} for service {service_id} by {changed_by}")
            return new_config
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create configuration: {str(e)}")
            raise DatabaseError("Failed to create configuration") from e
            
    async def get_configuration(self, config_id: int) -> ServiceConfiguration:
        result = await self.db.execute(select(ServiceConfiguration).where(ServiceConfiguration.id == config_id))
        config = result.scalar_one_or_none()
        
        if not config:
            raise ConfigurationNotFoundError(config_id)
            
        # Decrypt if needed
        if config.is_encrypted:
            config.config_value = decrypt_data(config.config_value)
            
        return config
        
    async def update_configuration(
        self, 
        config_id: int, 
        config_key: Optional[str], 
        config_value: Optional[str], 
        is_encrypted: Optional[bool],
        changed_by: str
    ) -> ServiceConfiguration:
        config = await self.get_configuration(config_id)
        
        if config_key is not None:
            config.config_key = config_key
            
        if config_value is not None:
            # Handle encryption change
            if is_encrypted is not None and is_encrypted != config.is_encrypted:
                if is_encrypted:
                    config_value = encrypt_data(config_value)
                else:
                    config_value = decrypt_data(config.config_value)
                config.is_encrypted = is_encrypted
                
            elif config.is_encrypted:
                config_value = encrypt_data(config_value)
            config.config_value = config_value
            
        config.changed_by = changed_by
        
        await self.db.commit()
        await self.db.refresh(config)
        
        logger.info(f"Updated configuration {config_id} by {changed_by}")
        return config
        
    async def list_configurations(self, service_id: int) -> List[ServiceConfiguration]:
        result = await self.db.execute(
            select(ServiceConfiguration).where(ServiceConfiguration.service_id == service_id)
        )
        configs = result.scalars().all()
        
        # Decrypt values that are encrypted
        for config in configs:
            if config.is_encrypted:
                config.config_value = decrypt_data(config.config_value)
                
        return configs
        
    async def delete_configuration(self, config_id: int) -> bool:
        config = await self.get_configuration(config_id)
        await self.db.delete(config)
        await self.db.commit()
        
        logger.info(f"Deleted configuration {config_id}")
        return True
```