```python
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.applications.models import Application
from mortgage_underwriting.modules.applications.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate
)
from mortgage_underwriting.modules.applications.services import ApplicationService


router = APIRouter(prefix="/api/v1/applications", tags=["Applications"])


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new mortgage application."""
    service = ApplicationService(db)
    try:
        return await service.create_application(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": getattr(e, 'code', 'UNKNOWN_ERROR')}
        )


@router.get("/", response_model=List[ApplicationResponse])
async def list_applications(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),  # FIXED: Capped limit enforcement
    db: AsyncSession = Depends(get_async_session),
):
    """List all applications with pagination support."""
    service = ApplicationService(db)
    return await service.get_applications(skip=skip, limit=limit)


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get an application by ID."""
    service = ApplicationService(db)
    try:
        return await service.get_application_by_id(application_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": getattr(e, 'code', 'NOT_FOUND')}
        )


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """Partially update an application."""
    service = ApplicationService(db)
    try:
        return await service.update_application(application_id, payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": getattr(e, 'code', 'UPDATE_FAILED')}
        )
```