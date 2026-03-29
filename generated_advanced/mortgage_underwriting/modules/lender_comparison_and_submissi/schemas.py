from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_validator

# --- LENDER SCHEMAS ---


class LenderBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., pattern="^(bank|credit_union|monoline|private|mfc)$")
    is_active: bool = True
    logo_url: Optional[str] = Field(None, max_length=500)
    submission_email: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=5000)


class LenderCreate(LenderBase):
    pass


class LenderUpdate(LenderBase):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[str] = Field(None, pattern="^(bank|credit_union|monoline|private|mfc)$")


class LenderResponse(LenderBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: datetime


# --- LENDER PRODUCT SCHEMAS ---


class LenderProductBase(BaseModel):
    lender_id: int = Field(..., gt=0)
    product_name: str = Field(..., min_length=1, max_length=255)
    mortgage_type: str = Field(..., pattern="^(fixed|variable|heloc)$")
    term_years: Decimal = Field(..., gt=0)
    rate: Decimal = Field(..., ge=0)
    rate_type: str = Field(..., pattern="^(posted|discounted|prime_plus)$")
    max_ltv_insured: Decimal = Field(..., ge=0, le=100)
    max_ltv_conventional: Decimal = Field(..., ge=0, le=100)
    max_amortization_insured: int = Field(..., ge=1, le=30)
    max_amortization_conventional: int = Field(..., ge=1, le=30)
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

    @field_validator('term_years')
    def validate_term_years(cls, v):
        if v <= 0:
            raise ValueError('Term years must be greater than 0')
        return v


class LenderProductCreate(LenderProductBase):
    pass


class LenderProductUpdate(LenderProductBase):
    lender_id: Optional[int] = Field(None, gt=0)
    product_name: Optional[str] = Field(None, min_length=1, max_length=255)
    mortgage_type: Optional[str] = Field(None, pattern="^(fixed|variable|heloc)$")
    rate_type: Optional[str] = Field(None, pattern="^(posted|discounted|prime_plus)$")


class LenderProductResponse(LenderProductBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: datetime


# --- LENDER SUBMISSION SCHEMAS ---


class LenderSubmissionBase(BaseModel):
    application_id: int = Field(..., gt=0)
    lender_id: int = Field(..., gt=0)
    product_id: Optional[int] = Field(None, gt=0)
    submitted_by: Optional[int] = Field(None, gt=0)
    status: str = Field("pending", pattern="^(pending|approved|declined|countered)$")
    lender_reference_number: Optional[str] = Field(None, max_length=100)
    lender_conditions: Optional[str] = Field(None, max_length=5000)
    approved_rate: Optional[Decimal] = Field(None, ge=0)
    approved_amount: Optional[Decimal] = Field(None, ge=0)
    expiry_date: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=5000)


class LenderSubmissionCreate(LenderSubmissionBase):
    pass


class LenderSubmissionUpdate(LenderSubmissionBase):
    application_id: Optional[int] = Field(None, gt=0)
    lender_id: Optional[int] = Field(None, gt=0)
    status: Optional[str] = Field(None, pattern="^(pending|approved|declined|countered)$")


class LenderSubmissionResponse(LenderSubmissionBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime


# --- MATCHING SCHEMAS ---


class LenderMatchRequest(BaseModel):
    application_id: int = Field(..., gt=0, description="FK to mortgage_applications table")
    client_id: int = Field(..., gt=0, description="FK to clients table")
    # Property
    purchase_price: Decimal = Field(..., gt=0, description="Property purchase price in CAD")
    down_payment: Decimal = Field(..., gt=0, description="Down payment amount in CAD")
    # Rates
    contract_rate: Decimal = Field(..., gt=0, description="Contract interest rate as percentage (e.g., 5.5 for 5.5%)")
    # Applicant Info
    gross_monthly_income: Decimal = Field(..., gt=0, description="Total gross monthly income in CAD")
    monthly_debts: Decimal = Field(0, ge=0, description="Total monthly debt obligations in CAD")
    condo_fees: Decimal = Field(0, ge=0, description="Monthly condominium fees in CAD")
    credit_score: int = Field(..., ge=300, le=900, description="Applicant's credit score")
    # Self-employed or rental income flags
    is_self_employed: bool = False
    has_rental_income: bool = False
    
    @property
    def loan_amount(self) -> Decimal:
        return self.purchase_price - self.down_payment
    
    @property
    def ltv_ratio(self) -> Decimal:
        if self.purchase_price <= 0:
            return Decimal('0')
        return (self.loan_amount / self.purchase_price) * 100


class LenderMatchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    product_id: int
    lender_id: int
    lender_name: str
    product_name: str
    rate: Decimal
    term_years: Decimal
    max_ltv_insured: Decimal
    max_ltv_conventional: Decimal
    max_amortization_insured: int
    max_amortization_conventional: int
    min_credit_score: int
    max_gds: Decimal
    max_tds: Decimal
    allows_self_employed: bool
    allows_rental_income: bool
    allows_gifted_down_payment: bool
    prepayment_privilege_percent: Decimal
    portability: bool
    assumability: bool
    lender_conditions: Optional[str] = None
    notes: Optional[str] = None


class SubmissionPackageRequest(BaseModel):
    application_id: int = Field(..., gt=0)
    uw_result_id: int = Field(..., gt=0)
    matched_products: List[LenderMatchResult]
    broker_notes: Optional[str] = Field(None, max_length=5000)