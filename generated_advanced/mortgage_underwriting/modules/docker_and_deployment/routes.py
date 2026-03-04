```python
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from .schemas import (
    DeploymentCreateRequest,
    DeploymentUpdateRequest,
    ServiceCreateRequest,
    ServiceConfigurationCreateRequest,
    DeploymentResponse,
    ServiceResponse,
    ServiceConfigurationResponse,
    DeploymentDetailResponse,
    ServiceWithConfigsResponse,
    DeploymentSummaryResponse
)
from .services import DeploymentService, ServiceService, ConfigurationService
from .exceptions import DeploymentNotFoundError, ServiceNotFoundError, ConfigurationNotFoundError
from common.database import get_db
from common.auth import get_current_user
from common.models import User
import logging


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/deployments", tags=["Deployments"])


async def get_deployment_service(db: AsyncSession = Depends(get_db)) -> DeploymentService:
    return DeploymentService(db)


async def get_service_service(db: AsyncSession = Depends(get_db)) -> ServiceService:
    return ServiceService(db)


async def get_config_service(db: AsyncSession = Depends(get_db)) -> ConfigurationService:
    return ConfigurationService(db)


@router.post("/", response_model=DeploymentResponse, status_code=201)
async def create_deployment(
    deployment_data: DeploymentCreateRequest,
    current_user: User = Depends(get_current_user),
    service: DeploymentService = Depends(get_deployment_service)
):
    """
    Create a new deployment.
    
    Args:
        deployment_data: Deployment creation data
        current_user: Authenticated user
        service: Deployment service instance
        
    Returns:
        Created deployment object
    """
    try:
        deployment = await service.create_deployment(deployment_data, current_user.username)
        return deployment
    except Exception as e:
        logger.error(f"Error creating deployment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create deployment")


@router.get("/{deployment_id}", response_model=DeploymentDetailResponse)
async def get_deployment(
    deployment_id: int = Path(..., gt=0, description="Deployment ID"),
    service: DeploymentService = Depends(get_deployment_service)
):
    """
    Get deployment details including its services.
    
    Args:
        deployment_id: ID of the deployment to retrieve
        service: Deployment service instance
        
    Returns:
        Deployment details with services
    """
    try:
        deployment = await service.get_deployment(deployment_id)
        services = await service.list_services(deployment_id)
        return DeploymentDetailResponse(
            **deployment.__dict__,
            services=[ServiceResponse(**s.__dict__) for s in services]
        )
    except DeploymentNotFoundError:
        raise HTTPException(status_code=404, detail="Deployment not found")
    except Exception as e:
        logger.error(f"Error retrieving deployment {deployment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve deployment")


@router.put("/{deployment_id}", response_model=DeploymentResponse)
async def update_deployment(
    deployment_id: int,
    update_data: DeploymentUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: DeploymentService = Depends(get_deployment_service)
):
    """
    Update an existing deployment.
    
    Args:
        deployment_id: ID of the deployment to update
        update_data: Fields to update
        current_user: Authenticated user
        service: Deployment service instance
        
    Returns:
        Updated deployment object
    """
    try:
        deployment = await service.update_deployment(deployment_id, update_data, current_user.username)
        return deployment
    except DeploymentNotFoundError:
        raise HTTPException(status_code=404, detail="Deployment not found")
    except Exception as e:
        logger.error(f"Error updating deployment {deployment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update deployment")


@router.get("/", response_model=List[DeploymentResponse])
async def list_deployments(
    environment: Optional[str] = Query(None, regex=r"^(development|staging|production)$"),
    service: DeploymentService = Depends(get_deployment_service)
):
    """
    List deployments with optional environment filter.
    
    Args:
        environment: Filter by environment
        service: Deployment service instance
        
    Returns:
        List of deployments
    """
    try:
        deployments = await service.list_deployments(environment)
        return [DeploymentResponse(**d.__dict__) for d in deployments]
    except Exception as e:
        logger.error(f"Error listing deployments: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list deployments")


@router.delete("/{deployment_id}", status_code=204)
async def delete_deployment(
    deployment_id: int,
    service: DeploymentService = Depends(get_deployment_service)
):
    """
    Delete a deployment and all its services.
    
    Args:
        deployment_id: ID of the deployment to delete
        service: Deployment service instance
    """
    try:
        await service.delete_deployment(deployment_id)
    except DeploymentNotFoundError:
        raise HTTPException(status_code=404, detail="Deployment not found")
    except Exception as e:
        logger.error(f"Error deleting deployment {deployment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete deployment")


@router.post("/{deployment_id}/services", response_model=ServiceResponse, status_code=201)
async def create_service(
    deployment_id: int,
    service_data: ServiceCreateRequest,
    current_user: User = Depends(get_current_user),
    service_svc: ServiceService = Depends(get_service_service)
):
    """
    Create a new service within a deployment.
    
    Args:
        deployment_id: ID of the parent deployment
        service_data: Service creation data
        current_user: Authenticated user
        service_svc: Service service instance
        
    Returns:
        Created service object
    """
    try:
        service_obj = await service_svc.create_service(deployment_id, service_data, current_user.username)
        return service_obj
    except Exception as e:
        logger.error(f"Error creating service: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create service")


@router.get("/services/{service_id}", response_model=ServiceWithConfigsResponse)
async def get_service_with_configs(
    service_id: int,
    service_svc: ServiceService = Depends(get_service_service),
    config_svc: ConfigurationService = Depends(get_config_service)
):
    """
    Get service details including its configurations.
    
    Args:
        service_id: ID of the service to retrieve
        service_svc: Service service instance
        config_svc: Configuration service instance
        
    Returns:
        Service details with configurations
    """
    try:
        service_obj = await service_svc.get_service(service_id)
        configs = await config_svc.list_configurations(service_id)
        return ServiceWithConfigsResponse(
            **service_obj.__dict__,
            configurations=[ServiceConfigurationResponse(**c.__dict__) for c in configs]
        )
    except ServiceNotFoundError:
        raise HTTPException(status_code=404, detail="Service not found")
    except Exception as e:
        logger.error(f"Error retrieving service {service_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve service")


@router.put("/services/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: int,
    update_data: ServiceCreateRequest,
    current_user: User = Depends(get_current_user),
    service_svc: ServiceService = Depends(get_service_service)
):
    """
    Update an existing service.
    
    Args:
        service_id: ID of the service to update
        update_data: Fields to update
        current_user: Authenticated user
        service_svc: Service service instance
        
    Returns:
        Updated service object
    """
    try:
        service_obj = await service_svc.update_service(service_id, update_data, current_user.username)
        return service_obj
    except ServiceNotFoundError:
        raise HTTPException(status_code=404, detail="Service not found")
    except Exception as e:
        logger.error(f"Error updating service {service_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update service")


@router.delete("/services/{service_id}", status_code=204)
async def delete_service(
    service_id: int,
    service_svc: ServiceService = Depends(get_service_service)
):
    """
    Delete a service and all its configurations.
    
    Args:
        service_id: ID of the service to delete
        service_svc: Service service instance
    """
    try:
        await service_svc.delete_service(service_id)
    except ServiceNotFoundError:
        raise HTTPException(status_code=404, detail="Service not found")
    except Exception as e:
        logger.error(f"Error deleting service {service_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete service")


@router.post("/services/{service_id}/configs", response_model=ServiceConfigurationResponse, status_code=201)
async def create_configuration(
    service_id: int,
    config_data: ServiceConfigurationCreateRequest,
    current_user: User = Depends(get_current_user),
    config_svc: ConfigurationService = Depends(get_config_service)
):
    """
    Create a new configuration for a service.
    
    Args:
        service_id: ID of the parent service
        config_data: Configuration creation data
        current_user: Authenticated user
        config_svc: Configuration service instance
        
    Returns:
        Created configuration object
    """
    try:
        config = await config_svc.create_configuration(service_id, config_data, current_user.username)
        return config
    except Exception as e:
        logger.error(f"Error creating configuration: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create configuration")


@router.put("/configs/{config_id}", response_model=ServiceConfigurationResponse)
async def update_configuration(
    config_id: int,
    config_key: Optional[str] = None,
    config_value: Optional[str] = None,
    is_encrypted: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    config_svc: ConfigurationService = Depends(get_config_service)
):
    """
    Update an existing configuration.
    
    Args:
        config_id: ID of the configuration to update
        config_key: New configuration key
        config_value: New configuration value
        is_encrypted: Whether the value should be encrypted
        current_user: Authenticated user
        config_svc: Configuration service instance
        
    Returns:
        Updated configuration object
    """
    try:
        config = await config_svc.update_configuration(
            config_id, config_key, config_value, is_encrypted, current_user.username
        )
        return config
    except ConfigurationNotFoundError:
        raise HTTPException(status_code=404, detail="Configuration not found")
    except Exception as e:
        logger.error(f"Error updating configuration {config_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update configuration")


@router.delete("/configs/{config_id}", status_code=204)
async def delete_configuration(
    config_id: int,
    config_svc: ConfigurationService = Depends(get_config_service)
):
    """
    Delete a configuration.
    
    Args:
        config_id: ID of the configuration to delete
        config_svc: Configuration service instance
    """
    try:
        await config_svc.delete_configuration(config_id)
    except ConfigurationNotFoundError:
        raise HTTPException(status_code=404, detail="Configuration not found")
    except Exception as e:
        logger.error(f"Error deleting configuration {config_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete configuration")


@router.get("/summary", response_model=DeploymentSummaryResponse)
async def get_deployment_summary(
    service: DeploymentService = Depends(get_deployment_service)
):
    """
    Get deployment summary statistics.
    
    Args:
        service: Deployment service instance
        
    Returns:
        Summary statistics about deployments
    """
    try:
        deployments = await service.list_deployments()
        
        total_deployments = len(deployments)
        active_deployments = sum(1 for d in deployments if d.is_active)
        environments = {}
        
        for deployment in deployments:
            env = deployment.environment
            environments[env] = environments.get(env, 0) + 1
            
        return DeploymentSummaryResponse(
            total_deployments=total_deployments,
            active_deployments=active_deployments,
            environments=environments
        )
    except Exception as e:
        logger.error(f"Error getting deployment summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get deployment summary")
```