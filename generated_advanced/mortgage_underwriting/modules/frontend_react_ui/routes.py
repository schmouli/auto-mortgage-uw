from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.frontend_react_ui.schemas import (
    FrontendUIModuleCreate,
    FrontendUIModuleUpdate,
    FrontendUIModuleResponse,
    UIComponentCreate,
    UIComponentUpdate
)
from mortgage_underwriting.modules.frontend_react_ui.services import FrontendUIService
from mortgage_underwriting.modules.frontend_react_ui.exceptions import FrontendUIError

router = APIRouter(prefix="/api/v1/ui", tags=["Frontend React UI"])


@router.post("/modules", response_model=FrontendUIModuleResponse, status_code=status.HTTP_201_CREATED)
async def create_ui_module(
    payload: FrontendUIModuleCreate,
    db: AsyncSession = Depends(get_async_session)
) -> FrontendUIModuleResponse:
    """Create a new frontend UI module."""
    service = FrontendUIService(db)
    try:
        return await service.create_module(payload)
    except FrontendUIError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": "FRONTEND_UI_ERROR"})


@router.get("/modules/{module_id}", response_model=FrontendUIModuleResponse)
async def get_ui_module(
    module_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> FrontendUIModuleResponse:
    """Get a specific frontend UI module by ID."""
    service = FrontendUIService(db)
    module = await service.get_module(module_id)
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": "Module not found", "error_code": "MODULE_NOT_FOUND"})
    return module


@router.get("/modules", response_model=List[FrontendUIModuleResponse])
async def list_ui_modules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_async_session)
) -> List[FrontendUIModuleResponse]:
    """List all frontend UI modules with pagination."""
    service = FrontendUIService(db)
    return await service.list_modules(skip=skip, limit=limit)


@router.put("/modules/{module_id}", response_model=FrontendUIModuleResponse)
async def update_ui_module(
    module_id: int,
    payload: FrontendUIModuleUpdate,
    db: AsyncSession = Depends(get_async_session)
) -> FrontendUIModuleResponse:
    """Update a frontend UI module."""
    service = FrontendUIService(db)
    updated = await service.update_module(module_id, payload)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": "Module not found", "error_code": "MODULE_NOT_FOUND"})
    return updated


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ui_module(
    module_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> None:
    """Delete a frontend UI module."""
    service = FrontendUIService(db)
    deleted = await service.delete_module(module_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": "Module not found", "error_code": "MODULE_NOT_FOUND"})


@router.post("/components", response_model=FrontendUIModuleResponse, status_code=status.HTTP_201_CREATED)
async def create_ui_component(
    payload: UIComponentCreate,
    db: AsyncSession = Depends(get_async_session)
) -> FrontendUIModuleResponse:
    """Create a new UI component."""
    service = FrontendUIService(db)
    try:
        component = await service.create_component(payload)
        return await service.get_module(component.module_id)
    except FrontendUIError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": "FRONTEND_UI_ERROR"})


@router.put("/components/{component_id}", response_model=FrontendUIModuleResponse)
async def update_ui_component(
    component_id: int,
    payload: UIComponentUpdate,
    db: AsyncSession = Depends(get_async_session)
) -> FrontendUIModuleResponse:
    """Update a UI component."""
    service = FrontendUIService(db)
    updated = await service.update_component(component_id, payload)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": "Component not found", "error_code": "COMPONENT_NOT_FOUND"})
    module = await service.get_module(updated.module_id)
    return module


@router.delete("/components/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ui_component(
    component_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> None:
    """Delete a UI component."""
    service = FrontendUIService(db)
    deleted = await service.delete_component(component_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": "Component not found", "error_code": "COMPONENT_NOT_FOUND"})