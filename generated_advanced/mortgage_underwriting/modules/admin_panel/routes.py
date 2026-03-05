from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.admin_panel.services import AdminPanelService
from mortgage_underwriting.modules.admin_panel.schemas import (
    AdminUserResponse, AdminUserCreate, AdminUserUpdate,
    SupportAgentResponse, SupportAgentCreate,
    RoleResponse, RoleCreate
)
from mortgage_underwriting.modules.admin_panel.exceptions import AdminPanelException

router = APIRouter(prefix="/api/v1/admin-panel", tags=["Admin Panel"])


@router.post("/users/", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    payload: AdminUserCreate,
    db: AsyncSession = Depends(get_async_session),
) -> AdminUserResponse:
    """Create a new admin user."""
    try:
        service = AdminPanelService(db)
        return await service.create_admin_user(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "ADMIN_USER_CREATION_FAILED", "message": str(e)}
        )


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_admin_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> AdminUserResponse:
    """Get an admin user by ID."""
    try:
        service = AdminPanelService(db)
        return await service.get_admin_user(user_id)
    except AdminPanelException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "ADMIN_USER_NOT_FOUND", "message": str(e)}
        )


@router.get("/users/", response_model=List[AdminUserResponse])
async def list_admin_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
) -> List[AdminUserResponse]:
    """List admin users with pagination."""
    try:
        service = AdminPanelService(db)
        users = await service.list_admin_users(skip=skip, limit=limit)
        return users
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "ADMIN_USERS_LIST_FAILED", "message": str(e)}
        )


@router.put("/users/{user_id}", response_model=AdminUserResponse)
async def update_admin_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: AsyncSession = Depends(get_async_session),
) -> AdminUserResponse:
    """Update an admin user."""
    try:
        service = AdminPanelService(db)
        return await service.update_admin_user(user_id, payload)
    except AdminPanelException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "ADMIN_USER_NOT_FOUND", "message": str(e)}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "ADMIN_USER_UPDATE_FAILED", "message": str(e)}
        )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> None:
    """Delete an admin user."""
    try:
        service = AdminPanelService(db)
        await service.delete_admin_user(user_id)
    except AdminPanelException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "ADMIN_USER_NOT_FOUND", "message": str(e)}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "ADMIN_USER_DELETION_FAILED", "message": str(e)}
        )


@router.post("/support-agents/", response_model=SupportAgentResponse, status_code=status.HTTP_201_CREATED)
async def create_support_agent(
    payload: SupportAgentCreate,
    db: AsyncSession = Depends(get_async_session),
) -> SupportAgentResponse:
    """Create a new support agent."""
    try:
        service = AdminPanelService(db)
        return await service.create_support_agent(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "SUPPORT_AGENT_CREATION_FAILED", "message": str(e)}
        )


@router.post("/roles/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    db: AsyncSession = Depends(get_async_session),
) -> RoleResponse:
    """Create a new role."""
    try:
        service = AdminPanelService(db)
        return await service.create_role(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "ROLE_CREATION_FAILED", "message": str(e)}
        )
```

```