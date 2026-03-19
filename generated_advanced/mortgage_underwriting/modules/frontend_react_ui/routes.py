from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.frontend.schemas import (
    FrontendComponentCreate,
    FrontendComponentUpdate,
    FrontendComponentResponse
)
from mortgage_underwriting.modules.frontend.services import FrontendComponentService
from mortgage_underwriting.modules.frontend.exceptions import ComponentNotFoundError

router = APIRouter(prefix="/api/v1/frontend/components", tags=["Frontend Components"])


@router.get("/", response_model=List[FrontendComponentResponse])
async def list_components(
    db: AsyncSession = Depends(get_async_session)
) -> List[FrontendComponentResponse]:
    service = FrontendComponentService(db)
    return await service.get_all_components()


@router.post("/", response_model=FrontendComponentResponse, status_code=status.HTTP_201_CREATED)
async def create_component(
    payload: FrontendComponentCreate,
    db: AsyncSession = Depends(get_async_session)
) -> FrontendComponentResponse:
    service = FrontendComponentService(db)
    return await service.create_component(payload)


@router.get("/{component_id}", response_model=FrontendComponentResponse)
async def get_component(
    component_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> FrontendComponentResponse:
    service = FrontendComponentService(db)
    try:
        return await service.get_component_by_id(component_id)
    except ComponentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{component_id}", response_model=FrontendComponentResponse)
async def update_component(
    component_id: int,
    payload: FrontendComponentUpdate,
    db: AsyncSession = Depends(get_async_session)
) -> FrontendComponentResponse:
    service = FrontendComponentService(db)
    try:
        return await service.update_component(component_id, payload)
    except ComponentNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))