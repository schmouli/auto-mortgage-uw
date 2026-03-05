from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from mortgage_underwriting.common.database import get_async_session
from .services import InfrastructureService
from .schemas import (
    InfrastructureProviderCreate,
    InfrastructureProviderUpdate,
    InfrastructureProviderResponse,
    DeploymentEventCreate,
    DeploymentEventUpdate,
    DeploymentEventResponse,
    DeploymentAuditCreate,
    DeploymentAuditResponse,
    DeploymentListQueryParams
)

router = APIRouter(prefix="/api/v1/infrastructure", tags=["Infrastructure Deployment"])

@router.post("/providers/", response_model=InfrastructureProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: InfrastructureProviderCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new infrastructure provider."""
    try:
        service = InfrastructureService(db)
        return await service.create_provider(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "PROVIDER_CREATION_FAILED", "detail": str(e)}
        )

@router.get("/providers/{provider_id}", response_model=InfrastructureProviderResponse)
async def get_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Retrieve an infrastructure provider by ID."""
    service = InfrastructureService(db)
    provider = await service.get_provider(provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PROVIDER_NOT_FOUND", "detail": f"Provider with ID {provider_id} not found"}
        )
    return provider

@router.put("/providers/{provider_id}", response_model=InfrastructureProviderResponse)
async def update_provider(
    provider_id: int,
    payload: InfrastructureProviderUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """Update an infrastructure provider."""
    service = InfrastructureService(db)
    provider = await service.update_provider(provider_id, payload)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "PROVIDER_NOT_FOUND", "detail": f"Provider with ID {provider_id} not found"}
        )
    return provider

@router.get("/providers/", response_model=List[InfrastructureProviderResponse])
async def list_providers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_async_session),
):
    """List infrastructure providers with pagination."""
    service = InfrastructureService(db)
    return await service.list_providers(skip, limit)

@router.post("/deployments/", response_model=DeploymentEventResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment_event(
    payload: DeploymentEventCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new deployment event."""
    try:
        service = InfrastructureService(db)
        return await service.create_deployment_event(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DEPLOYMENT_EVENT_CREATION_FAILED", "detail": str(e)}
        )

@router.get("/deployments/{event_id}", response_model=DeploymentEventResponse)
async def get_deployment_event(
    event_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Retrieve a deployment event by ID."""
    service = InfrastructureService(db)
    event = await service.get_deployment_event(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "DEPLOYMENT_EVENT_NOT_FOUND", "detail": f"Deployment event with ID {event_id} not found"}
        )
    return event

@router.get("/deployments/", response_model=List[DeploymentEventResponse])
async def list_deployment_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    provider_id: int = Query(None, gt=0),
    db: AsyncSession = Depends(get_async_session),
):
    """List deployment events with pagination and filtering."""
    query_params = DeploymentListQueryParams(skip=skip, limit=limit, provider_id=provider_id)
    service = InfrastructureService(db)
    return await service.list_deployment_events(query_params)

@router.put("/deployments/{event_id}", response_model=DeploymentEventResponse)
async def update_deployment_event(
    event_id: int,
    payload: DeploymentEventUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """Update a deployment event."""
    service = InfrastructureService(db)
    event = await service.update_deployment_event(event_id, payload)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "DEPLOYMENT_EVENT_NOT_FOUND", "detail": f"Deployment event with ID {event_id} not found"}
        )
    return event

@router.post("/audits/", response_model=DeploymentAuditResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment_audit(
    payload: DeploymentAuditCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new deployment audit record."""
    try:
        service = InfrastructureService(db)
        return await service.create_deployment_audit(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "DEPLOYMENT_AUDIT_CREATION_FAILED", "detail": str(e)}
        )

@router.get("/audits/{audit_id}", response_model=DeploymentAuditResponse)
async def get_deployment_audit(
    audit_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Retrieve a deployment audit record by ID."""
    service = InfrastructureService(db)
    audit = await service.get_deployment_audit(audit_id)
    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "DEPLOYMENT_AUDIT_NOT_FOUND", "detail": f"Deployment audit with ID {audit_id} not found"}
        )
    return audit
```

```