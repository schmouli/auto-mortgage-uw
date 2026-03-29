from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from .schemas import (
    UserListResponse,
    UserDeactivateRequest,
    UserDeactivateResponse,
    UserRoleChangeRequest,
    UserRoleChangeResponse,
    LenderCreate,
    LenderUpdate,
    LenderProductCreate,
    LenderProductUpdate,
    AuditLogResponse
)
from .services import AdminService
from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.auth.dependencies import get_current_active_admin_user
from mortgage_underwriting.modules.auth.models import User

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


# Dependency to inject service


async def get_admin_service(db: AsyncSession = Depends(get_async_session)) -> AdminService:
    return AdminService(db)


# --- USER MANAGEMENT ---

@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=200),
    status: Optional[str] = Query(None, regex="^(active|inactive|pending)$"),
    role: Optional[str] = Query(None, regex="^(admin|underwriter|read_only)$"),
    search: Optional[str] = None,
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(get_current_active_admin_user)
):
    """List all users with filtering and pagination."""
    try:
        return await service.list_users(page=page, limit=limit, status=status, role=role, search=search)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "VALIDATION_ERROR"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"detail": str(e), "error_code": "ADMIN_LIST_USERS_ERROR"})


@router.put("/users/{user_id}/deactivate", response_model=UserDeactivateResponse)
async def deactivate_user(
    user_id: int,
    payload: UserDeactivateRequest,
    service: AdminService = Depends(get_admin_service),
    admin_user: User = Depends(get_current_active_admin_user)
):
    """Deactivate a user account."""
    try:
        return await service.deactivate_user(user_id, payload, admin_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "VALIDATION_ERROR"})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "ADMIN_DEACTIVATE_USER_ERROR"})


@router.put("/users/{user_id}/role", response_model=UserRoleChangeResponse)
async def change_user_role(
    user_id: int,
    payload: UserRoleChangeRequest,
    service: AdminService = Depends(get_admin_service),
    admin_user: User = Depends(get_current_active_admin_user)
):
    """Change a user's role."""
    try:
        return await service.change_user_role(user_id, payload, admin_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "VALIDATION_ERROR"})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "ADMIN_CHANGE_ROLE_ERROR"})


# --- LENDER MANAGEMENT ---

@router.post("/lenders", response_model=LenderCreate, status_code=status.HTTP_201_CREATED)
async def create_lender(
    payload: LenderCreate,
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(get_current_active_admin_user)
):
    """Create a new lender."""
    try:
        return await service.create_lender(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "ADMIN_CREATE_LENDER_ERROR"})


@router.put("/lenders/{lender_id}", response_model=LenderUpdate)
async def update_lender(
    lender_id: int,
    payload: LenderUpdate,
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(get_current_active_admin_user)
):
    """Update an existing lender."""
    try:
        return await service.update_lender(lender_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "VALIDATION_ERROR"})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "ADMIN_UPDATE_LENDER_ERROR"})


@router.post("/lenders/{lender_id}/products", response_model=LenderProductCreate, status_code=status.HTTP_201_CREATED)
async def add_product(
    lender_id: int,
    payload: LenderProductCreate,
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(get_current_active_admin_user)
):
    """Add a product to a lender."""
    try:
        payload.lender_id = lender_id
        return await service.add_product(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "ADMIN_ADD_PRODUCT_ERROR"})


@router.put("/lenders/{lender_id}/products/{prod_id}", response_model=LenderProductUpdate)
async def update_product(
    lender_id: int,
    prod_id: int,
    payload: LenderProductUpdate,
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(get_current_active_admin_user)
):
    """Update a lender product."""
    try:
        return await service.update_product(prod_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "VALIDATION_ERROR"})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "ADMIN_UPDATE_PRODUCT_ERROR"})


@router.delete("/lenders/{lender_id}/products/{prod_id}")
async def deactivate_product(
    lender_id: int,
    prod_id: int,
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(get_current_active_admin_user)
):
    """Deactivate a lender product."""
    try:
        result = await service.deactivate_product(prod_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "VALIDATION_ERROR"})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "ADMIN_DEACTIVATE_PRODUCT_ERROR"})


# --- AUDIT LOG ---

@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def view_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=100),
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(get_current_active_admin_user)
):
    """View audit log entries."""
    try:
        logs, _ = await service.get_audit_logs(page=page, limit=limit, entity_type=entity_type, action=action)
        return logs
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "VALIDATION_ERROR"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"detail": str(e), "error_code": "ADMIN_VIEW_AUDIT_LOGS_ERROR"})


# --- FINTRAC REPORTS ---

@router.get("/fintrac/reports")
async def get_fintrac_reports(
    service: AdminService = Depends(get_admin_service),
    _: User = Depends(get_current_active_admin_user)
):
    """Get all FINTRAC reports."""
    try:
        return await service.get_fintrac_reports()
    except Exception as e:
        raise HTTPException(status_code=500, detail={"detail": str(e), "error_code": "ADMIN_GET_FINTRAC_REPORTS_ERROR"})