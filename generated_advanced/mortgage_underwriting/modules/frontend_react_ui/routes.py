from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from . import services, schemas

router = APIRouter(prefix="/api/v1/ui", tags=["Frontend React UI"])

# UI Component Routes

@router.post("/components", response_model=schemas.UiComponentResponse, status_code=status.HTTP_201_CREATED)
async def create_ui_component(
    payload: schemas.UiComponentCreate,
    db: AsyncSession = Depends(get_async_session),
) -> schemas.UiComponentResponse:
    """Create a new reusable UI component."""
    service = services.UiComponentService(db)
    try:
        return await service.create_component(payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": "UI_COMPONENT_CREATE_FAILED"})

@router.get("/components/{component_id}", response_model=schemas.UiComponentResponse)
async def read_ui_component(
    component_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> schemas.UiComponentResponse:
    """Get a specific UI component by ID."""
    service = services.UiComponentService(db)
    try:
        return await service.get_component(component_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": str(e), "error_code": "UI_COMPONENT_NOT_FOUND"})

@router.put("/components/{component_id}", response_model=schemas.UiComponentResponse)
async def update_ui_component(
    component_id: int,
    payload: schemas.UiComponentUpdate,
    db: AsyncSession = Depends(get_async_session),
) -> schemas.UiComponentResponse:
    """Update an existing UI component."""
    service = services.UiComponentService(db)
    try:
        return await service.update_component(component_id, payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": "UI_COMPONENT_UPDATE_FAILED"})

@router.delete("/components/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ui_component(
    component_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> None:
    """Delete a UI component."""
    service = services.UiComponentService(db)
    try:
        await service.delete_component(component_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": "UI_COMPONENT_DELETE_FAILED"})

# UI Page Routes

@router.post("/pages", response_model=schemas.UiPageResponse, status_code=status.HTTP_201_CREATED)
async def create_ui_page(
    payload: schemas.UiPageCreate,
    db: AsyncSession = Depends(get_async_session),
) -> schemas.UiPageResponse:
    """Create a new UI page with its components."""
    service = services.UiPageService(db)
    try:
        return await service.create_page(payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": "UI_PAGE_CREATE_FAILED"})

@router.get("/pages/{page_id}", response_model=schemas.UiPageResponse)
async def read_ui_page(
    page_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> schemas.UiPageResponse:
    """Get a specific UI page by ID including its components."""
    service = services.UiPageService(db)
    try:
        return await service.get_page_with_components(page_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": str(e), "error_code": "UI_PAGE_NOT_FOUND"})

@router.get("/pages/route/{route_path:path}", response_model=schemas.UiPageResponse)
async def read_ui_page_by_route(
    route_path: str,
    db: AsyncSession = Depends(get_async_session),
) -> schemas.UiPageResponse:
    """Get a specific UI page by its route path."""
    service = services.UiPageService(db)
    try:
        # Ensure leading slash
        if not route_path.startswith('/'):
            route_path = '/' + route_path
        return await service.get_page_by_route(route_path)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": str(e), "error_code": "UI_PAGE_ROUTE_NOT_FOUND"})

@router.get("/pages", response_model=List[schemas.UiPageResponse])
async def list_ui_pages(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
) -> List[schemas.UiPageResponse]:
    """List all UI pages with pagination."""
    service = services.UiPageService(db)
    pages, _ = await service.list_pages(skip=skip, limit=limit)
    return pages

@router.put("/pages/{page_id}", response_model=schemas.UiPageResponse)
async def update_ui_page(
    page_id: int,
    payload: schemas.UiPageUpdate,
    db: AsyncSession = Depends(get_async_session),
) -> schemas.UiPageResponse:
    """Update an existing UI page."""
    service = services.UiPageService(db)
    try:
        return await service.update_page(page_id, payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": "UI_PAGE_UPDATE_FAILED"})

@router.delete("/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ui_page(
    page_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> None:
    """Delete a UI page."""
    service = services.UiPageService(db)
    try:
        await service.delete_page(page_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": "UI_PAGE_DELETE_FAILED"})