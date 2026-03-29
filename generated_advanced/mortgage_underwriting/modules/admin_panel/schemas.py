from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

# --- USER MANAGEMENT SCHEMAS ---


class UserListResponseItem(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    role: str
    status: str
    last_login_at: Optional[datetime] = None
    created_at: datetime


class UserListResponse(BaseModel):
    items: List[UserListResponseItem]
    total: int
    page: int
    limit: int


class UserDeactivateRequest(BaseModel):
    reason: str = Field(..., max_length=500)
    notify_user: bool = True


class UserDeactivateResponse(BaseModel):
    id: int
    status: str
    deactivated_at: datetime
    deactivated_by: int


class UserRoleChangeRequest(BaseModel):
    new_role: str = Field(..., pattern="^(admin|underwriter|read_only)$")
    justification: str = Field(..., max_length=500)


class UserRoleChangeResponse(BaseModel):
    id: int
    role: str
    updated_at: datetime


# --- LENDER MANAGEMENT SCHEMAS ---


class LenderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., pattern="^(bank|credit_union|monoline|private|mfc)$")
    is_active: bool = True
    logo_url: Optional[str] = Field(None, max_length=500)
    submission_email: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=5000)


class LenderUpdate(LenderCreate):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[str] = Field(None, pattern="^(bank|credit_union|monoline|private|mfc)$")


class LenderProductCreate(BaseModel):
    lender_id: int = Field(..., gt=0)
    product_name: str = Field(..., min_length=1, max_length=255)
    mortgage_type: str = Field(..., pattern="^(fixed|variable|heloc)$")
    term_years: Decimal = Field(..., gt=0)
    rate: Decimal = Field(..., ge=0)
    rate_type: str = Field(..., pattern="^(posted|discounted|prime_plus)$")
    max_ltv_insured: Decimal = Field(..., ge=0, le=100)
    max_ltv_conventional: Decimal = Field(..., ge=0, le=100)
    max_amortization_insured: int = Field(..., gt=0, le=30)
    max_amortization_conventional: int = Field(..., gt=0, le=30)
    min_down_payment: Decimal = Field(..., ge=0, le=100)
    max_loan_amount: Decimal = Field(..., gt=0)
    insurance_required: bool = False
    insurance_premium_rate: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = Field(None, max_length=2000)


class LenderProductUpdate(LenderProductCreate):
    pass


# --- AUDIT LOG SCHEMAS ---

# FIXED: Removed extra fields from AuditLogResponse to match DB schema
# According to issue report, this schema had extraneous fields not present in model
# Only keeping fields that are actually part of the AuditLog model

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: Optional[int]
    action: str
    entity_type: str
    entity_id: int
    old_value: Optional[str]
    new_value: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime