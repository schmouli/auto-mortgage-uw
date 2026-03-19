from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.client_intake.schemas import (
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
    ApplicationSummaryResponse
)
from mortgage_underwriting.modules.client_intake.services import ClientIntakeService

router = APIRouter(prefix="/api/v1/applications", tags=["Client Intake & Applications"])


def get_service(db: AsyncSession = Depends(get_async_session)) -> ClientIntakeService:
    return ClientIntakeService(db)


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,
    service: ClientIntakeService = Depends(get_service)
):
    """Create a new mortgage application (draft status)."""
    try:
        return await service.create_application(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "APPLICATION_CREATE_ERROR"}
        )


@router.get("/", response_model=List[ApplicationResponse])
async def list_applications(
    client_id: Optional[int] = Query(None, description="Filter by client ID"),
    status: Optional[str] = Query(None, description="Filter by application status"),
    limit: int = Query(100, le=100, description="Max number of results"),
    offset: int = Query(0, description="Pagination offset"),
    service: ClientIntakeService = Depends(get_service)
):
    """List mortgage applications with optional filters."""
    try:
        return await service.list_applications(client_id=client_id, status=status, limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "APPLICATION_LIST_ERROR"}
        )


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: int,
    service: ClientIntakeService = Depends(get_service)
):
    """Get a specific mortgage application by ID."""
    try:
        return await service.get_application(application_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "APPLICATION_NOT_FOUND"}
        )


@router.put("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    service: ClientIntakeService = Depends(get_service)
):
    """Update an existing mortgage application."""
    try:
        return await service.update_application(application_id, payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "APPLICATION_UPDATE_ERROR"}
        )


@router.post("/{application_id}/submit", response_model=ApplicationResponse)
async def submit_application(
    application_id: int,
    service: ClientIntakeService = Depends(get_service)
):
    """Submit an application for underwriting."""
    try:
        return await service.submit_application(application_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "APPLICATION_SUBMIT_ERROR"}
        )


@router.get("/{application_id}/summary", response_model=ApplicationSummaryResponse)
async def get_application_summary(
    application_id: int,
    service: ClientIntakeService = Depends(get_service)
):
    """Get a PDF-ready summary of an application."""
    try:
        summary = await service.get_application_summary(application_id)
        return ApplicationSummaryResponse(**summary)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "APPLICATION_SUMMARY_ERROR"}
        )