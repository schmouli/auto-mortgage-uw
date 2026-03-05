from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from mortgage_underwriting.modules.docker_deployment.schemas import (
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
from mortgage_underwriting.modules.docker_deployment.services import DeploymentService, ServiceService, ConfigurationService
from mortgage_underwriting.modules.docker_deployment.exceptions import DeploymentNotFoundError, ServiceNotFoundError, ConfigurationNotFoundError
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.common.security import verify_token
import structlog

logger = structlog.get_logger()  # FIXED: Using structlog instead of logging
router = APIRouter(prefix="/api/v1/deployments", tags=["Deployments"])


async def get_deployment_service(db: AsyncSession = Depends(get_async_session)) -> DeploymentService:
    return DeploymentService(db)


async def get_service_service(db: AsyncSession = Depends(get_async_session)) -> ServiceService:
    return ServiceService(db)


async def get_config_service(db: AsyncSession = Depends(get_async_session)) -> ConfigurationService:
    return ConfigurationService(db)


@router.post("/", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    deployment_data: DeploymentCreateRequest,
    current_user: dict = Depends(verify_token),
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
        deployment = await service.create_deployment(deployment_data, current_user.get("username"))
        logger.info("deployment_endpoint_create_success", deployment_id=deployment.id)
        return deployment
    except Exception as e:
        logger.error("deployment_endpoint_create_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{deployment_id}", response_model=DeploymentDetailResponse)
async def get_deployment(
    deployment_id: int = Path(..., ge=1),
    service: DeploymentService = Depends(get_deployment_service)
):
    """
    Get a specific deployment by ID.
    """
    try:
        deployment = await service.get_deployment(deployment_id)
        logger.info("deployment_endpoint_get_success", deployment_id=deployment_id)
        return deployment
    except DeploymentNotFoundError as e:
        logger.warning("deployment_endpoint_get_not_found", deployment_id=deployment_id)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("deployment_endpoint_get_error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=List[DeploymentSummaryResponse])
async def list_deployments(
    environment: Optional[str] = Query(None, regex=r"^(development|staging|production)$"),
    is_active: Optional[bool] = Query(None),
    service: DeploymentService = Depends(get_deployment_service)
):
    """
    List deployments with optional filtering.
    """
    try:
        deployments = await service.list_deployments(environment=environment, is_active=is_active)
        logger.info("deployment_endpoint_list_success", count=len(deployments))
        return deployments
    except Exception as e:
        logger.error("deployment_endpoint_list_error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{deployment_id}", response_model=DeploymentResponse)
async def update_deployment(
    deployment_id: int,
    update_data: DeploymentUpdateRequest,
    current_user: dict = Depends(verify_token),
    service: DeploymentService = Depends(get_deployment_service)
):
    """
    Update a deployment.
    """
    try:
        deployment = await service.update_deployment(deployment_id, update_data, current_user.get("username"))
        logger.info("deployment_endpoint_update_success", deployment_id=deployment_id)
        return deployment
    except DeploymentNotFoundError as e:
        logger.warning("deployment_endpoint_update_not_found", deployment_id=deployment_id)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("deployment_endpoint_update_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: int,
    service: DeploymentService = Depends(get_deployment_service)
):
    """
    Delete a deployment.
    """
    try:
        await service.delete_deployment(deployment_id)
        logger.info("deployment_endpoint_delete_success", deployment_id=deployment_id)
        return
    except DeploymentNotFoundError as e:
        logger.warning("deployment_endpoint_delete_not_found", deployment_id=deployment_id)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("deployment_endpoint_delete_error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{deployment_id}/services", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    deployment_id: int,
    service_data: ServiceCreateRequest,
    service_svc: ServiceService = Depends(get_service_service)
):
    """
    Create a new service in a deployment.
    """
    try:
        service = await service_svc.create_service(deployment_id, service_data)
        logger.info("service_endpoint_create_success", service_id=service.id)
        return service
    except Exception as e:
        logger.error("service_endpoint_create_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/services/{service_id}", response_model=ServiceWithConfigsResponse)
async def get_service(
    service_id: int,
    service_svc: ServiceService = Depends(get_service_service),
    config_svc: ConfigurationService = Depends(get_config_service)
):
    """
    Get a specific service with its configurations.
    """
    try:
        service = await service_svc.get_service(service_id)
        configs = await config_svc.list_configurations(service_id)
        
        result = ServiceWithConfigsResponse(
            **service.__dict__,
            configurations=configs
        )
        
        logger.info("service_endpoint_get_success", service_id=service_id)
        return result
    except ServiceNotFoundError as e:
        logger.warning("service_endpoint_get_not_found", service_id=service_id)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("service_endpoint_get_error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/services/{service_id}/configurations", response_model=ServiceConfigurationResponse, status_code=status.HTTP_201_CREATED)
async def create_configuration(
    service_id: int,
    config_data: ServiceConfigurationCreateRequest,
    config_svc: ConfigurationService = Depends(get_config_service)
):
    """
    Create a new configuration for a service.
    """
    try:
        config = await config_svc.create_configuration(service_id, config_data)
        logger.info("configuration_endpoint_create_success", config_id=config.id)
        return config
    except Exception as e:
        logger.error("configuration_endpoint_create_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/configurations/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_configuration(
    config_id: int,
    config_svc: ConfigurationService = Depends(get_config_service)
):
    """
    Delete a configuration.
    """
    try:
        await config_svc.delete_configuration(config_id)
        logger.info("configuration_endpoint_delete_success", config_id=config_id)
        return
    except ConfigurationNotFoundError as e:
        logger.warning("configuration_endpoint_delete_not_found", config_id=config_id)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("configuration_endpoint_delete_error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
```

```