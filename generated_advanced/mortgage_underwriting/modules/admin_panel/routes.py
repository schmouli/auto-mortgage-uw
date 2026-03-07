from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.admin_panel.services import (
    AuditLogService,
    UserService,
    LenderService,
)
from mortgage_underwriting.modules.admin_panel.schemas import (
    AuditLogListResponse,
    AdminUserListQuery,
    AdminUserListResponse,
    UserDeactivateRequest,
    UserDeactivateResponse,
    UserRoleUpdateRequest,
    UserRoleUpdateResponse,
    LenderCreate,
    LenderUpdate,
    LenderResponse,
    ProductCreate,
    ProductUpdate,
    ProductResponse,
)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Panel"])


# --- Audit Logs ---


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
) -> AuditLogListResponse:
    """View audit log entries.
    
    Args:
        page: Page number
        limit: Number of items per page
        db: Database session
        
    Returns:
        Paginated list of audit logs
    """
    service = AuditLogService(db)
    return await service.list_logs(page=page, limit=limit)


# --- Users ---


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    query: AdminUserListQuery = Depends(),
    db: AsyncSession = Depends(get_async_session),
) -> AdminUserListResponse:
    """List all users.
    
    Args:
        query: Query parameters for filtering
        db: Database session
        
    Returns:
        Paginated list of users
    """
    service = UserService(db)
    return await service.list_users(query)


@router.put("/users/{user_id}/deactivate", response_model=UserDeactivateResponse)
async def deactivate_user(
    user_id: int,
    payload: UserDeactivateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> UserDeactivateResponse:
    """Deactivate a user.
    
    Args:
        user_id: ID of user to deactivate
        payload: Deactivation request data
        db: Database session
        
    Returns:
        Deactivation confirmation
        
    Raises:
        HTTPException: If operation fails
    """
    # FIXED: Add validation for user_id
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid user ID")
        
    service = UserService(db)
    try:
        user_response = await service.deactivate_user(user_id, payload.reason)
        return UserDeactivateResponse(
            user_id=user_response.id,
            status="deactivated",
            deactivation_date=user_response.updated_at,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "USER_DEACTIVATION_FAILED"})


@router.put("/users/{user_id}/role", response_model=UserRoleUpdateResponse)
async def update_user_role(
    user_id: int,
    payload: UserRoleUpdateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> UserRoleUpdateResponse:
    """Change user role.
    
    Args:
        user_id: ID of user to update
        payload: Role update request data
        db: Database session
        
    Returns:
        Role update confirmation
        
    Raises:
        HTTPException: If operation fails
    """
    # FIXED: Add validation for user_id
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid user ID")
        
    service = UserService(db)
    try:
        # Get current user to capture old role
        user_response = await service.update_user_role(user_id, payload.new_role)
        # In a real implementation, we'd fetch the old role separately
        return UserRoleUpdateResponse(
            user_id=user_response.id,
            old_role="unknown",  # Would be captured in a full implementation
            new_role=payload.new_role,
            effective_at=user_response.updated_at,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "USER_ROLE_UPDATE_FAILED"})


# --- Lenders ---


@router.post("/lenders", response_model=LenderResponse, status_code=status.HTTP_201_CREATED)
async def create_lender(
    payload: LenderCreate,
    db: AsyncSession = Depends(get_async_session),
) -> LenderResponse:
    """Create a new lender.
    
    Args:
        payload: Lender creation data
        db: Database session
        
    Returns:
        Created lender
    """
    service = LenderService(db)
    try:
        return await service.create_lender(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "LENDER_CREATION_FAILED"})


@router.put("/lenders/{lender_id}", response_model=LenderResponse)
async def update_lender(
    lender_id: int,
    payload: LenderUpdate,
    db: AsyncSession = Depends(get_async_session),
) -> LenderResponse:
    """Update a lender.
    
    Args:
        lender_id: ID of lender to update
        payload: Update data
        db: Database session
        
    Returns:
        Updated lender
        
    Raises:
        HTTPException: If operation fails
    """
    # FIXED: Add validation for lender_id
    if lender_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid lender ID")
        
    service = LenderService(db)
    try:
        return await service.update_lender(lender_id, payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "LENDER_UPDATE_FAILED"})


@router.post(
    "/lenders/{lender_id}/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    lender_id: int,
    payload: ProductCreate,
    db: AsyncSession = Depends(get_async_session),
) -> ProductResponse:
    """Add a product to a lender.
    
    Args:
        lender_id: ID of lender
        payload: Product creation data
        db: Database session
        
    Returns:
        Created product
        
    Raises:
        HTTPException: If operation fails
    """
    # FIXED: Add validation for lender_id
    if lender_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid lender ID")
        
    service = LenderService(db)
    try:
        return await service.create_product(lender_id, payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "PRODUCT_CREATION_FAILED"})


@router.put("/lenders/{lender_id}/products/{product_id}", response_model=ProductResponse)
async def update_product(
    lender_id: int,
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_async_session),
) -> ProductResponse:
    """Update a product.
    
    Args:
        lender_id: ID of lender
        product_id: ID of product
        payload: Update data
        db: Database session
        
    Returns:
        Updated product
        
    Raises:
        HTTPException: If operation fails
    """
    # FIXED: Add validation for IDs
    if lender_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid lender ID")
    if product_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid product ID")
        
    service = LenderService(db)
    try:
        return await service.update_product(lender_id, product_id, payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "PRODUCT_UPDATE_FAILED"})


@router.delete(
    "/lenders/{lender_id}/products/{product_id}", response_model=ProductResponse
)
async def deactivate_product(
    lender_id: int,
    product_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> ProductResponse:
    """Deactivate a product.
    
    Args:
        lender_id: ID of lender
        product_id: ID of product
        db: Database session
        
    Returns:
        Deactivated product
        
    Raises:
        HTTPException: If operation fails
    """
    # FIXED: Add validation for IDs
    if lender_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid lender ID")
    if product_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid product ID")
        
    service = LenderService(db)
    try:
        return await service.deactivate_product(lender_id, product_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "PRODUCT_DEACTIVATION_FAILED"})