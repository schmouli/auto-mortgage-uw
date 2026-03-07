from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, EmailStr

# --- Audit Log Schemas ---

class AuditLogBase(BaseModel):
    """Base audit log schema with common fields."""

    entity_type: str = Field(
        ..., min_length=1, max_length=50, description="Entity table name"
    )
    entity_id: int = Field(..., gt=0, description="Row ID of changed entity")
    action: str = Field(
        ..., pattern="^(CREATE|UPDATE|DELETE)$", description="Type of change"
    )
    reason: Optional[str] = Field(
        None, max_length=500, description="Why the change occurred"
    )


class AuditLogCreate(AuditLogBase):
    """Audit log creation request."""

    changed_by: Optional[int] = Field(None, description="User ID who made the change")
    old_values: Optional[str] = Field(None, max_length=2000)
    new_values: Optional[str] = Field(None, max_length=2000)
    ip_address: Optional[str] = Field(None, description="IP address of the requester")
    user_agent: Optional[str] = Field(None, description="User agent string")


class AuditLogResponse(AuditLogBase):
    """Audit log response schema with timestamps."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Unique audit log ID")
    changed_by: Optional[int] = None
    old_values: Optional[str] = None
    new_values: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = Field(..., description="Timestamp of the change")


class AuditLogListResponse(BaseModel):
    """Paginated list of audit logs."""

    model_config = ConfigDict(from_attributes=True)

    logs: List[AuditLogResponse]
    total: int
    page: int
    limit: int


# --- User Schemas ---

class AdminUserListQuery(BaseModel):
    """Query parameters for listing users."""

    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    limit: int = Field(50, ge=1, le=100, description="Items per page (max 100)")
    role: Optional[str] = Field(
        None, pattern="^(broker|client|admin|underwriter|super_admin)$"
    )
    is_active: Optional[bool] = Field(None, description="Filter by active status")


class UserDeactivateRequest(BaseModel):
    """Request to deactivate a user."""

    reason: str = Field(
        ..., min_length=5, max_length=500, description="Reason for deactivation"
    )
    requires_approval: bool = Field(
        False, description="Whether approval is needed before deactivating"
    )


class UserDeactivateResponse(BaseModel):
    """Response after deactivating a user."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    status: str
    deactivation_date: datetime


class UserRoleUpdateRequest(BaseModel):
    """Request to update a user's role."""

    new_role: str = Field(
        ..., pattern="^(broker|client|admin|underwriter|super_admin)$"
    )
    justification: str = Field(
        ..., min_length=10, max_length=1000, description="Justification for role change"
    )


class UserRoleUpdateResponse(BaseModel):
    """Response after updating a user's role."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    old_role: str
    new_role: str
    effective_at: datetime


class AdminUserResponse(BaseModel):
    """User details returned to admin."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    phone: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AdminUserListResponse(BaseModel):
    """Paginated list of users."""

    model_config = ConfigDict(from_attributes=True)

    users: List[AdminUserResponse]
    total: int
    page: int
    limit: int


# --- Lender Schemas ---

class LenderBase(BaseModel):
    """Base fields for a lender."""

    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    contact_email: EmailStr


class LenderCreate(LenderBase):
    """Request to create a new lender."""

    pass


class LenderUpdate(BaseModel):
    """Request to update a lender."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    contact_email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class LenderResponse(LenderBase):
    """Response containing lender details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- Product Schemas ---

class ProductBase(BaseModel):
    """Base fields for a product."""

    name: str = Field(..., min_length=1, max_length=255)
    rate: Decimal = Field(..., ge=0, description="Annual interest rate (e.g., 0.0525)")
    max_ltv: Decimal = Field(
        ..., ge=0, le=100, description="Maximum Loan-to-Value ratio (e.g., 95.00)"
    )
    insurance_required: bool


class ProductCreate(ProductBase):
    """Request to create a new product."""

    pass


class ProductUpdate(BaseModel):
    """Request to update a product."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    rate: Optional[Decimal] = Field(None, ge=0)
    max_ltv: Optional[Decimal] = Field(None, ge=0, le=100)
    insurance_required: Optional[bool] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    """Response containing product details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    """Paginated list of products."""

    model_config = ConfigDict(from_attributes=True)

    products: List[ProductResponse]
    total: int
    page: int
    limit: int