from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


# --- Lender Schemas ---


class LenderBase(BaseModel):
    name: str = Field(..., max_length=255)
    type: str = Field(..., pattern="^(bank|credit_union|monoline|private|mfc)$")
    is_active: bool = True
    logo_url: Optional[str] = Field(None, max_length=500)
    submission_email: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class LenderCreate(LenderBase):
    pass


class LenderUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    type: Optional[str] = Field(None, pattern="^(bank|credit_union|monoline|private|mfc)$")
    is_active: Optional[bool] = None
    logo_url: Optional[str] = Field(None, max_length=500)
    submission_email: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class LenderSchema(LenderBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: datetime


class LenderListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    lenders: List[LenderSchema]


# --- Lender Product Schemas ---


class LenderProductBase(BaseModel):
    product_name: str = Field(..., max_length=255)
    mortgage_type: str = Field(..., pattern="^(fixed|variable|heloc)$")
    term_years: int = Field(..., gt=0)
    rate: Decimal = Field(..., ge=0)
    rate_type: str = Field(..., pattern="^(posted|discounted|prime_plus)$")
    max_ltv_insured: Decimal = Field(..., ge=0, le=100)
    max_ltv_conventional: Decimal = Field(..., ge=0, le=100)
    max_amortization_insured: int = Field(..., gt=0)
    max_amortization_conventional: int = Field(..., gt=0)
    min_credit_score: int = Field(..., ge=300, le=900)
    max_gds: Decimal = Field(..., ge=0, le=100)
    max_tds: Decimal = Field(..., ge=0, le=100)
    allows_self_employed: bool = False
    allows_rental_income: bool = False
    allows_gifted_down_payment: bool = False
    prepayment_privilege_percent: Decimal = Field(..., ge=0, le=100)
    portability: bool = False
    assumability: bool = False
    is_active: bool = True
    effective_date: datetime
    expiry_date: Optional[datetime] = None


class LenderProductCreate(LenderProductBase):
    pass


class LenderProductUpdate(BaseModel):
    product_name: Optional[str] = Field(None, max_length=255)
    mortgage_type: Optional[str] = Field(None, pattern="^(fixed|variable|heloc)$")
    term_years: Optional[int] = Field(None, gt=0)
    rate: Optional[Decimal] = Field(None, ge=0)
    rate_type: Optional[str] = Field(None, pattern="^(posted|discounted|prime_plus)$")
    max_ltv_insured: Optional[Decimal] = Field(None, ge=0, le=100)
    max_ltv_conventional: Optional[Decimal] = Field(None, ge=0, le=100)
    max_amortization_insured: Optional[int] = Field(None, gt=0)
    max_amortization_conventional: Optional[int] = Field(None, gt=0)
    min_credit_score: Optional[int] = Field(None, ge=300, le=900)
    max_gds: Optional[Decimal] = Field(None, ge=0, le=100)
    max_tds: Optional[Decimal] = Field(None, ge=0, le=100)
    allows_self_employed: Optional[bool] = None
    allows_rental_income: Optional[bool] = None
    allows_gifted_down_payment: Optional[bool] = None
    prepayment_privilege_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    portability: Optional[bool] = None
    assumability: Optional[bool] = None
    is_active: Optional[bool] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None


class LenderProductSchema(LenderProductBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    lender_id: int
    created_at: datetime
    updated_at: datetime


class LenderProductListResponse(BaseModel):
    lender_id: int
    lender_name: str
    products: List[LenderProductSchema]


# --- Lender Submission Schemas ---


class LenderSubmissionBase(BaseModel):
    application_id: int = Field(..., gt=0)
    lender_id: int = Field(..., gt=0)
    product_id: int = Field(..., gt=0)
    submitted_by: int = Field(..., gt=0)
    status: str = Field("pending", pattern="^(pending|approved|declined|countered)$")
    lender_reference_number: Optional[str] = Field(None, max_length=100)
    lender_conditions: Optional[str] = None
    approved_rate: Optional[Decimal] = Field(None, ge=0)
    approved_amount: Optional[Decimal] = Field(None, ge=0)
    expiry_date: Optional[datetime] = None
    notes: Optional[str] = None


class LenderSubmissionCreate(LenderSubmissionBase):
    pass


class LenderSubmissionUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(pending|approved|declined|countered)$")
    lender_reference_number: Optional[str] = Field(None, max_length=100)
    lender_conditions: Optional[str] = None
    approved_rate: Optional[Decimal] = Field(None, ge=0)
    approved_amount: Optional[Decimal] = Field(None, ge=0)
    expiry_date: Optional[datetime] = None
    notes: Optional[str] = None


class LenderSubmissionSchema(LenderSubmissionBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime


class LenderSubmissionListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    submissions: List[LenderSubmissionSchema]


# --- Matcher Schemas ---


class LenderMatchRequest(BaseModel):
    application_id: int = Field(..., gt=0)
    client_id: int = Field(..., gt=0)
    property_value: Decimal = Field(..., gt=0)
    down_payment: Decimal = Field(..., ge=0)
    annual_property_tax: Decimal = Field(..., ge=0)
    monthly_heating_cost: Decimal = Field(..., ge=0)
    monthly_condo_fees: Decimal = Field(0, ge=0)
    gross_monthly_income: Decimal = Field(..., gt=0)
    total_monthly_debts: Decimal = Field(0, ge=0)
    contract_rate: Decimal = Field(..., ge=0)
    credit_score: int = Field(..., ge=300, le=900)
    amortization_years: int = Field(..., gt=0, le=30)


class MatchedLenderProduct(BaseModel):
    lender_product_id: int
    lender_id: int
    lender_name: str
    product_name: str
    rate: Decimal
    max_ltv_insured: Decimal
    max_ltv_conventional: Decimal
    max_amortization_insured: int
    max_amortization_conventional: int
    allows_self_employed: bool
    allows_rental_income: bool
    allows_gifted_down_payment: bool
    prepayment_privilege_percent: Decimal
    portability: bool
    assumability: bool
    lender_conditions: Optional[str] = None


class LenderMatchResponse(BaseModel):
    matches: List[MatchedLenderProduct]