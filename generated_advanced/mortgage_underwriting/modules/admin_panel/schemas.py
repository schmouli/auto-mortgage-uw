from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

# User Schemas


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime


class UserListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    items: List[UserResponse]
    total: int
    page: int
    page_size: int


class UserRoleUpdate(BaseModel):
    role: str = Field(..., pattern="^(applicant|underwriter|admin|super_admin)$")

# Lender Schemas


class LenderBase(BaseModel):
    name: str = Field(..., max_length=255)


class LenderCreate(LenderBase):
    pass


class LenderUpdate(LenderBase):
    is_active: bool


class LenderResponse(LenderBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

# Product Schemas


class ProductBase(BaseModel):
    name: str = Field(..., max_length=255)
    min_loan_amount: Decimal = Field(..., gt=0)
    max_loan_amount: Decimal = Field(..., gt=0)
    interest_rate: Decimal = Field(..., ge=0, le=1)  # Rate as decimal (e.g., 0.035 for 3.5%)
    term_months: int = Field(..., gt=0, le=360)  # Max 30 years


class ProductCreate(ProductBase):
    pass


class ProductUpdate(ProductBase):
    is_active: bool


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

# Audit Log Schemas


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    user_id: Optional[int]
    action: str
    entity_type: str
    entity_id: int
    old_value: Optional[str]
    new_value: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    # FIXED: Removed extra fields that were not in schema parity with DBA review


class AuditLogListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int

# FINTRAC Report Schemas


class FintracReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    report_type: str
    generated_at: datetime
    file_path: str
    status: str