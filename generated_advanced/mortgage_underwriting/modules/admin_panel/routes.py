from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from fastapi import APIRouter, Depends, status, Query, Request, HTTPException

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.admin.schemas import (
    AdminUserListQuery, AdminUserResponse, UserDeactivateRequest,
    UserRoleUpdateRequest, UserStatusResponse, LenderCreate, LenderUpdate,
    LenderProductCreate, LenderProductUpdate, AuditLogResponse, FintracReportResponse
)
from mortgage_underwriting.modules.admin.services import AdminService
from mortgage_underwriting.modules.auth.models import User

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Panel"])


def get_current_admin(request: Request) -> User:
    # In real implementation, extract user from auth token
    # This is a placeholder for proper authentication
    return User(id=1, email="admin@example.com", role="admin")


def get_admin_service(db: AsyncSession = Depends(get_async_session)) -> AdminService:
    return AdminService(db)


@router.get("/users", response_model=List[AdminUserResponse])
async def list_users(
    query: AdminUserListQuery = Depends(),
    service: AdminService = Depends(get_admin_service)
) -> List[AdminUserResponse]:
    """List all users with optional filtering and pagination."""
    return await service.list_users(query)


@router.put("/users/{user_id}/deactivate", response_model=UserStatusResponse)
async def deactivate_user(
    user_id: int,
    payload: UserDeactivateRequest,
    service: AdminService = Depends(get_admin_service),
    current_admin: User = Depends(get_current_admin)
) -> UserStatusResponse:
    """Deactivate a user account."""
    if current_admin.role != "admin":
        raise HTTPException(status_code=403, detail={"detail": "Only admins can deactivate users", "error_code": "ADMIN_004"})
    return await service.deactivate_user(user_id, payload, current_admin.id)


@router.put("/users/{user_id}/role", response_model=AdminUserResponse)
async def update_user_role(
    user_id: int,
    payload: UserRoleUpdateRequest,
    service: AdminService = Depends(get_admin_service),
    current_admin: User = Depends(get_current_admin)
) -> AdminUserResponse:
    """Change a user's role."""
    if current_admin.role != "admin":
        raise HTTPException(status_code=403, detail={"detail": "Only admins can update roles", "error_code": "ADMIN_004"})
    return await service.update_user_role(user_id, payload, current_admin.id)


@router.post("/lenders", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_lender(
    payload: LenderCreate,
    service: AdminService = Depends(get_admin_service),
    current_admin: User = Depends(get_current_admin)
) -> dict:
    """Create a new lender."""
    if current_admin.role != "admin":
        raise HTTPException(status_code=403, detail={"detail": "Only admins can create lenders", "error_code": "ADMIN_004"})
    result = await service.create_lender(payload)
    return {"message": "Lender created successfully", "lender_id": result.id}


@router.put("/lenders/{lender_id}", response_model=dict)
async def update_lender(
    lender_id: int,
    payload: LenderUpdate,
    service: AdminService = Depends(get_admin_service),
    current_admin: User = Depends(get_current_admin)
) -> dict:
    """Update an existing lender."""
    if current_admin.role != "admin":
        raise HTTPException(status_code=403, detail={"detail": "Only admins can update lenders", "error_code": "ADMIN_004"})
    result = await service.update_lender(lender_id, payload)
    return {"message": "Lender updated successfully", "lender_id": result.id}


@router.post("/lenders/{lender_id}/products", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_product_to_lender(
    lender_id: int,
    payload: LenderProductCreate,
    service: AdminService = Depends(get_admin_service),
    current_admin: User = Depends(get_current_admin)
) -> dict:
    """Add a product to a lender."""
    if current_admin.role != "admin":
        raise HTTPException(status_code=403, detail={"detail": "Only admins can add products", "error_code": "ADMIN_004"})
    result = await service.add_product_to_lender(lender_id, payload)
    return {"message": "Product added successfully", "product_id": result.id}


@router.put("/lenders/{lender_id}/products/{product_id}", response_model=dict)
async def update_lender_product(
    lender_id: int,
    product_id: int,
    payload: LenderProductUpdate,
    service: AdminService = Depends(get_admin_service),
    current_admin: User = Depends(get_current_admin)
) -> dict:
    """Update a lender product."""
    if current_admin.role != "admin":
        raise HTTPException(status_code=403, detail={"detail": "Only admins can update products", "error_code": "ADMIN_004"})
    result = await service.update_lender_product(lender_id, product_id, payload)
    return {"message": "Product updated successfully", "product_id": result.id}


@router.delete("/lenders/{lender_id}/products/{product_id}")
async def deactivate_lender_product(
    lender_id: int,
    product_id: int,
    service: AdminService = Depends(get_admin_service),
    current_admin: User = Depends(get_current_admin)
) -> dict:
    """Deactivate a lender product."""
    if current_admin.role != "admin":
        raise HTTPException(status_code=403, detail={"detail": "Only admins can deactivate products", "error_code": "ADMIN_004"})
    await service.deactivate_lender_product(lender_id, product_id)
    return {"message": "Product deactivated successfully"}


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def view_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    service: AdminService = Depends(get_admin_service),
    current_admin: User = Depends(get_current_admin)
) -> List[AuditLogResponse]:
    """View audit logs."""
    if current_admin.role != "admin":
        raise HTTPException(status_code=403, detail={"detail": "Only admins can view audit logs", "error_code": "ADMIN_004"})
    return await service.list_audit_logs(page, limit)


@router.get("/fintrac/reports", response_model=List[FintracReportResponse])
async def get_fintrac_reports(
    service: AdminService = Depends(get_admin_service),
    current_admin: User = Depends(get_current_admin)
) -> List[FintracReportResponse]:
    """Get all FINTRAC reports."""
    if current_admin.role != "admin":
        raise HTTPException(status_code=403, detail={"detail": "Only admins can view FINTRAC reports", "error_code": "ADMIN_004"})
    return await service.get_fintrac_reports()