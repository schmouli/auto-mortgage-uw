from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class UserRole(str, Enum):
    broker = "broker"
    client = "client"
    admin = "admin"
    underwriter = "underwriter"


class AdminUserListQuery(BaseModel):
    page: int = Field(ge=1, default=1)
    limit: int = Field(ge=1, le=100, default=20)
    search: Optional[str] = Field(None, max_length=100)  # email or name prefix
    role: Optional[UserRole] = None


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]


class UserDeactivateRequest(BaseModel):
    reason: str = Field(..., min_length=10, max_length=500)
    notify_user: bool = True


class UserRoleUpdateRequest(BaseModel):
    new_role: UserRole
    justification: str = Field(..., min_length=10, max_length=500)


class UserStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    user_id: int
    is_active: bool
    deactivated_at: datetime
    deactivated_by: int


class LenderCreate(BaseModel):
    name: str = Field(..., max_length=255)
    type: str = Field(..., pattern="^(bank|credit_union|monoline|private|mfc)$")
    is_active: bool = True
    logo_url: Optional[str] = Field(None, max_length=500)
    submission_email: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class LenderUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    type: Optional[str] = Field(None, pattern="^(bank|credit_union|monoline|private|mfc)$")
    is_active: Optional[bool] = None
    logo_url: Optional[str] = Field(None, max_length=500)
    submission_email: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class LenderProductCreate(BaseModel):
    product_name: str = Field(..., max_length=255)
    mortgage_type: str = Field(..., pattern="^(fixed|variable|heloc)$")
    term_years: int = Field(..., gt=0)
    rate: Decimal = Field(..., ge=0)
    rate_type: str = Field(..., pattern="^(fixed|variable)$")
    max_ltv_insured: Decimal = Field(..., ge=0, le=100)
    max_loan_amount: Optional[Decimal] = Field(None, gt=0)
    min_credit_score: Optional[int] = Field(None, ge=300, le=900)
    is_active: bool = True
    notes: Optional[str] = None


class LenderProductUpdate(BaseModel):
    product_name: Optional[str] = Field(None, max_length=255)
    mortgage_type: Optional[str] = Field(None, pattern="^(fixed|variable|heloc)$")
    term_years: Optional[int] = Field(None, gt=0)
    rate: Optional[Decimal] = Field(None, ge=0)
    rate_type: Optional[str] = Field(None, pattern="^(fixed|variable)$")
    max_ltv_insured: Optional[Decimal] = Field(None, ge=0, le=100)
    max_loan_amount: Optional[Decimal] = Field(None, gt=0)
    min_credit_score: Optional[int] = Field(None, ge=300, le=900)
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    # FIXED: Removed extra fields to match DB schema
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


class FintracReportResponse(BaseModel):
    report_id: str
    generated_at: datetime
    total_records: int
    high_risk_count: int
    total_value_cad: Decimal