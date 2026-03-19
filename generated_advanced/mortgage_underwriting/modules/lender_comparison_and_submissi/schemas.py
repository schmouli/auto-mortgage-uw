from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Literal

from pydantic import BaseModel, Field, ConfigDict, validator

# Enums
LenderTypeEnum = Literal['bank', 'credit_union', 'monoline', 'private', 'mfc']
MortgageTypeEnum = Literal['fixed', 'variable', 'heloc']
RateTypeEnum = Literal['posted', 'discounted', 'prime_plus']
SubmissionStatusEnum = Literal['pending', 'approved', 'declined', 'countered']


# Lender Schemas


class LenderBase(BaseModel):
    name: str = Field(..., max_length=255, min_length=1)
    type: LenderTypeEnum
    is_active: bool = True
    logo_url: Optional[str] = Field(None, max_length=500, pattern=r'^https?://')
    submission_email: Optional[str] = Field(None, max_length=255, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    notes: Optional[str] = Field(None, max_length=2000)


class LenderCreate(LenderBase):
    pass


class LenderUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255, min_length=1)
    type: Optional[LenderTypeEnum] = None
    is_active: Optional[bool] = None
    logo_url: Optional[str] = Field(None, max_length=500, pattern=r'^https?://')
    submission_email: Optional[str] = Field(None, max_length=255, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    notes: Optional[str] = Field(None, max_length=2000)


class LenderResponse(LenderBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: datetime


# Lender Product Schemas


class LenderProductBase(BaseModel):
    lender_id: int = Field(..., gt=0)
    product_name: str = Field(..., max_length=255, min_length=1)
    mortgage_type: MortgageTypeEnum
    term_years: int = Field(..., gt=0, le=30)
    rate: Decimal = Field(..., ge=0, le=1)  # Rate as percentage (0-100%) or decimal?
    rate_type: RateTypeEnum
    max_ltv_insured: Decimal = Field(..., ge=0, le=1)
    max_ltv_conventional: Decimal = Field(..., ge=0, le=1)
    max_amortization_insured: int = Field(..., gt=0, le=35)
    max_amortization_conventional: int = Field(..., gt=0, le=35)
    min_credit_score: int = Field(..., ge=300, le=900)
    max_gds: Decimal = Field(..., ge=0, le=1)
    max_tds: Decimal = Field(..., ge=0, le=1)
    allows_self_employed: bool = False
    allows_rental_income: bool = False
    allows_gifted_down_payment: bool = False
    prepayment_privilege_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    portability: bool = False
    assumability: bool = False
    is_active: bool = True
    effective_date: datetime
    expiry_date: Optional[datetime] = None
    
    @validator('max_ltv_insured')
    def validate_ltv_insured(cls, v):
        if v > Decimal('1') or v < Decimal('0'):
            raise ValueError('max_ltv_insured must be between 0 and 1')
        return v
        
    @validator('max_ltv_conventional')
    def validate_ltv_conventional(cls, v):
        if v > Decimal('1') or v < Decimal('0'):
            raise ValueError('max_ltv_conventional must be between 0 and 1')
        return v


class LenderProductCreate(LenderProductBase):
    pass


class LenderProductUpdate(BaseModel):
    product_name: Optional[str] = Field(None, max_length=255, min_length=1)
    mortgage_type: Optional[MortgageTypeEnum] = None
    term_years: Optional[int] = Field(None, gt=0, le=30)
    rate: Optional[Decimal] = Field(None, ge=0, le=1)
    rate_type: Optional[RateTypeEnum] = None
    max_ltv_insured: Optional[Decimal] = Field(None, ge=0, le=1)
    max_ltv_conventional: Optional[Decimal] = Field(None, ge=0, le=1)
    max_amortization_insured: Optional[int] = Field(None, gt=0, le=35)
    max_amortization_conventional: Optional[int] = Field(None, gt=0, le=35)
    min_credit_score: Optional[int] = Field(None, ge=300, le=900)
    max_gds: Optional[Decimal] = Field(None, ge=0, le=1)
    max_tds: Optional[Decimal] = Field(None, ge=0, le=1)
    allows_self_employed: Optional[bool] = None
    allows_rental_income: Optional[bool] = None
    allows_gifted_down_payment: Optional[bool] = None
    prepayment_privilege_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    portability: Optional[bool] = None
    assumability: Optional[bool] = None
    is_active: Optional[bool] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None


class LenderProductResponse(LenderProductBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: datetime


# Lender Submission Schemas


class LenderSubmissionBase(BaseModel):
    application_id: int = Field(..., gt=0)
    lender_id: int = Field(..., gt=0)
    product_id: Optional[int] = Field(None, gt=0)
    submitted_by: Optional[int] = Field(None, gt=0)
    submitted_at: datetime
    status: SubmissionStatusEnum = 'pending'
    lender_reference_number: Optional[str] = Field(None, max_length=100)
    lender_conditions: Optional[List[str]] = Field(None, max_items=50)
    approved_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    approved_amount: Optional[Decimal] = Field(None, ge=0)
    expiry_date: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=2000)


class LenderSubmissionCreate(LenderSubmissionBase):
    pass


class LenderSubmissionUpdate(BaseModel):
    status: Optional[SubmissionStatusEnum] = None
    lender_reference_number: Optional[str] = Field(None, max_length=100)
    lender_conditions: Optional[List[str]] = Field(None, max_items=50)
    approved_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    approved_amount: Optional[Decimal] = Field(None, ge=0)
    expiry_date: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=2000)


class LenderSubmissionResponse(LenderSubmissionBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: datetime


# Match Request Schema


class LenderMatchRequest(BaseModel):
    application_id: int = Field(..., gt=0, description="Underwriting application ID")
    property_value: Decimal = Field(..., gt=0, description="Property value in CAD")
    loan_amount: Decimal = Field(..., gt=0, description="Requested loan amount in CAD")
    contract_rate: Decimal = Field(..., gt=0, le=1, description="Contract interest rate as decimal (e.g., 0.0595)")
    amortization_years: int = Field(..., ge=5, le=30, description="Amortization period in years (5-30)")
    gross_monthly_income: Decimal = Field(..., gt=0, description="Total gross monthly income in CAD")
    monthly_debt_payments: Decimal = Field(..., ge=0, description="Total monthly debt payments in CAD")
    property_taxes_annual: Decimal = Field(..., ge=0, description="Annual property taxes in CAD")
    heating_costs_monthly: Decimal = Field(..., gt=0, description="Monthly heating costs in CAD")
    down_payment_amount: Decimal = Field(..., gt=0, description="Down payment amount in CAD")
    credit_score: int = Field(..., ge=300, le=900, description="Applicant's credit score")
    allows_self_employed: bool = False
    allows_rental_income: bool = False
    allows_gifted_down_payment: bool = False


class LenderMatchResponseItem(BaseModel):
    lender_id: int
    lender_name: str
    product_id: int
    product_name: str
    rate: Decimal
    term_years: int
    max_ltv_insured: Decimal
    max_ltv_conventional: Decimal
    qualifies: bool
    reason: Optional[str] = None


class LenderMatchResponse(BaseModel):
    matches: List[LenderMatchResponseItem]
    total_matches: int