from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.application import services, schemas

router = APIRouter(prefix="/api/v1/applications", tags=["Client Intake & Application"])


@router.post("/", response_model=schemas.MortgageApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: schemas.MortgageApplicationCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new mortgage application."""
    try:
        service = services.ApplicationService(db)
        return await service.create_application(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error_code": "APPLICATION_CREATE_FAILED", "message": str(e)})


@router.get("/", response_model=List[schemas.MortgageApplicationResponse])
async def list_applications(
    client_id: Optional[int] = Query(None, description="Filter by client ID"),
    broker_id: Optional[int] = Query(None, description="Filter by broker ID"),
    limit: int = Query(100, le=100, description="Max number of results"),
    offset: int = Query(0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_async_session),
):
    """List mortgage applications with optional filters."""
    try:
        service = services.ApplicationService(db)
        apps, _ = await service.list_applications(client_id=client_id, broker_id=broker_id, limit=limit, offset=offset)
        return apps
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error_code": "APPLICATION_LIST_FAILED", "message": str(e)})


@router.get("/{app_id}", response_model=schemas.MortgageApplicationResponse)
async def get_application(
    app_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific mortgage application by ID."""
    try:
        service = services.ApplicationService(db)
        return await service.get_application(app_id)
    except services.NotFoundError as e:
        raise HTTPException(status_code=404, detail={"error_code": "APPLICATION_NOT_FOUND", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error_code": "APPLICATION_GET_FAILED", "message": str(e)})


@router.put("/{app_id}", response_model=schemas.MortgageApplicationResponse)
async def update_application(
    app_id: int,
    payload: schemas.MortgageApplicationUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """Update an existing mortgage application."""
    try:
        service = services.ApplicationService(db)
        return await service.update_application(app_id, payload)
    except services.NotFoundError as e:
        raise HTTPException(status_code=404, detail={"error_code": "APPLICATION_NOT_FOUND", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error_code": "APPLICATION_UPDATE_FAILED", "message": str(e)})


@router.post("/{app_id}/submit", response_model=schemas.MortgageApplicationResponse)
async def submit_application(
    app_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Submit an application for underwriting."""
    try:
        service = services.ApplicationService(db)
        return await service.submit_application(app_id)
    except services.NotFoundError as e:
        raise HTTPException(status_code=404, detail={"error_code": "APPLICATION_NOT_FOUND", "message": str(e)})
    except services.AppException as e:
        raise HTTPException(status_code=400, detail={"error_code": "APPLICATION_SUBMIT_DENIED", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error_code": "APPLICATION_SUBMIT_FAILED", "message": str(e)})


@router.get("/{app_id}/summary", response_model=schemas.ApplicationSummaryResponse)
async def get_application_summary(
    app_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get a summary of the application suitable for PDF generation."""
    try:
        service = services.ApplicationService(db)
        return await service.get_summary(app_id)
    except services.NotFoundError as e:
        raise HTTPException(status_code=404, detail={"error_code": "APPLICATION_NOT_FOUND", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error_code": "APPLICATION_SUMMARY_FAILED", "message": str(e)})