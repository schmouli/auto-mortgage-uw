from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.intake.schemas import (
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
    ApplicationSummaryResponse
)
from mortgage_underwriting.modules.intake.services import IntakeService

router = APIRouter(prefix="/api/v1/applications", tags=["Client Intake & Application"])

# NOTE: Authentication dependency would be added in real implementation
# For example: current_user = Depends(get_current_active_user)

@router.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    # current_user: User = Depends(get_current_active_user),  # Would require auth
    db: AsyncSession = Depends(get_async_session),
) -> ClientResponse:
    """Create a new client profile with encrypted PII."""
    service = IntakeService(db)
    # In real implementation: user_id would come from current_user.id
    return await service.create_client(user_id=1, payload=payload)  # Placeholder user_id

@router.put("/clients/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_async_session),
) -> ClientResponse:
    """Update an existing client profile."""
    service = IntakeService(db)
    return await service.update_client(client_id, payload)

@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,
    # current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> ApplicationResponse:
    """Create a new mortgage application."""
    service = IntakeService(db)
    # In real implementation: role and user_id would come from current_user
    return await service.create_application(user_role="client", user_id=1, payload=payload)  # Placeholder

@router.get("/", response_model=List[ApplicationResponse])
async def list_applications(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_session),
) -> List[ApplicationResponse]:
    """List mortgage applications with pagination."""
    # This would be implemented with proper filtering and authorization
    pass  # Implementation placeholder

@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> ApplicationResponse:
    """Get a specific mortgage application."""
    # This would include authorization checks
    pass  # Implementation placeholder

@router.put("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    db: AsyncSession = Depends(get_async_session),
) -> ApplicationResponse:
    """Update a mortgage application."""
    service = IntakeService(db)
    return await service.update_application(application_id, payload)

@router.post("/{application_id}/submit", response_model=ApplicationResponse)
async def submit_application(
    application_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> ApplicationResponse:
    """Submit an application for underwriting."""
    service = IntakeService(db)
    return await service.submit_application(application_id)

@router.get("/{application_id}/summary", response_model=ApplicationSummaryResponse)
async def get_application_summary(
    application_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> ApplicationSummaryResponse:
    """Get a summary of the application for PDF generation."""
    service = IntakeService(db)
    summary_data = await service.get_application_summary(application_id)
    return ApplicationSummaryResponse(**summary_data)