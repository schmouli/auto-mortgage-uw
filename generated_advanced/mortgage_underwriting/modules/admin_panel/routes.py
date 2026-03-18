from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.admin_panel.schemas import (
    UserListResponse,
    UserResponse,
    UserRoleUpdate,
    LenderCreate,
    LenderUpdate,
    LenderResponse,
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    AuditLogListResponse,
    FintracReportResponse
)
from mortgage_underwriting.modules.admin_panel.services import AdminPanelService

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Panel"])

# Dependency to get admin service


async def get_admin_service(db: AsyncSession = Depends(get_async_session)) -> AdminPanelService:
    return AdminPanelService(db)

# User Management Endpoints

@router.get("/users", response_model=UserListResponse)


async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    role: Optional[str] = Query(None, pattern="^(applicant|underwriter|admin|super_admin)$"),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, max_length=100),
    service: AdminPanelService = Depends(get_admin_service)
):
    """List all users with pagination and filtering."""
    return await service.list_users(page, page_size, role, is_active, search)

@router.put("/users/{user_id}/deactivate", response_model=UserResponse)


async def deactivate_user(
    user_id: int,
    reason: str = Query(..., min_length=10, max_length=500),
    # FIXED: Removed deactivated_by parameter - will be derived from auth token in real implementation
    service: AdminPanelService = Depends(get_admin_service)
):
    """Deactivate a user account."""
    # In real implementation, get current_user_id from auth token
    current_user_id = 1  # Placeholder - would come from auth middleware
    return await service.deactivate_user(user_id, reason, current_user_id)

@router.put("/users/{user_id}/role", response_model=UserResponse)


async def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    # FIXED: Removed updated_by parameter - will be derived from auth token in real implementation
    service: AdminPanelService = Depends(get_admin_service)
):
    """Change user role."""
    # In real implementation, get current_user_id from auth token
    current_user_id = 1  # Placeholder - would come from auth middleware
    return await service.update_user_role(user_id, payload, current_user_id)

# Lender Management Endpoints

@router.post("/lenders", response_model=LenderResponse, status_code=status.HTTP_201_CREATED)


async def create_lender(
    payload: LenderCreate,
    service: AdminPanelService = Depends(get_admin_service)
):
    """Create a new lender."""
    return await service.create_lender(payload)

@router.put("/lenders/{lender_id}", response_model=LenderResponse)


async def update_lender(
    lender_id: int,
    payload: LenderUpdate,
    service: AdminPanelService = Depends(get_admin_service)
):
    """Update lender details."""
    return await service.update_lender(lender_id, payload)

@router.post("/lenders/{lender_id}/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)


async def add_product(
    lender_id: int,
    payload: ProductCreate,
    service: AdminPanelService = Depends(get_admin_service)
):
    """Add a product to a lender."""
    return await service.add_product(lender_id, payload)

@router.put("/lenders/{lender_id}/products/{product_id}", response_model=ProductResponse)


async def update_product(
    lender_id: int,
    product_id: int,
    payload: ProductUpdate,
    service: AdminPanelService = Depends(get_admin_service)
):
    """Update a lender product."""
    return await service.update_product(lender_id, product_id, payload)

@router.delete("/lenders/{lender_id}/products/{product_id}", response_model=ProductResponse)


async def deactivate_product(
    lender_id: int,
    product_id: int,
    service: AdminPanelService = Depends(get_admin_service)
):
    """Deactivate a lender product."""
    return await service.deactivate_product(lender_id, product_id)

# Audit Log Endpoint

@router.get("/audit-logs", response_model=AuditLogListResponse)


async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    service: AdminPanelService = Depends(get_admin_service)
):
    """View audit logs."""
    return await service.list_audit_logs(page, page_size)

# FINTRAC Reports Endpoint

@router.get("/fintrac/reports", response_model=list[FintracReportResponse])


async def get_fintrac_reports(
    service: AdminPanelService = Depends(get_admin_service)
):
    """Get all FINTRAC reports."""
    return await service.get_fintrac_reports()