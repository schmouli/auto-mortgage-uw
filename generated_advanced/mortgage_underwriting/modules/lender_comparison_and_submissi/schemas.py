```python
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Union
from pydantic import BaseModel, Field, validator
from enum import Enum


class LenderType(str, Enum):
    BANK = "bank"
    CREDIT_UNION = "credit_union"
    MONOLINE = "monoline"
    PRIVATE = "private"
    MFC = "mfc"


class MortgageType(str, Enum):
    FIXED = "fixed"
    VARIABLE = "variable"
    HELOC = "heloc"


class RateType(str, Enum):
    POSTED = "posted"
    DISCOUNTED = "discounted"
    PRIME_PLUS = "prime_plus"


class SubmissionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    COUNTERED = "countered"


# Request Schemas
class LenderCreateRequest(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the lender")
    type: LenderType = Field(..., description="Type of the lender")
    is_active: bool = Field(True, description="Whether the lender is active")
    logo_url: Optional[str] = Field(None, max_length=500, description="URL to the lender's logo")
    submission_email: Optional[str] = Field(None, max_length=255, description="Email address for submissions")
    notes: Optional[str] = Field(None, description="Additional notes about the lender")


class LenderUpdateRequest(LenderCreateRequest):
    pass


class LenderProductCreateRequest(BaseModel):
    lender_id: int = Field(..., gt=0, description="ID of the associated lender")
    product_name: str = Field(..., max_length=255, description="Name of the product")
    mortgage_type: MortgageType = Field(..., description="Type of mortgage")
    term_years: Optional[int] = Field(None, ge=1, le=30, description="Term length in years")
    rate: Decimal = Field(..., description="Interest rate percentage (e.g., 4.5)")
    rate_type: RateType = Field(..., description="How the rate is determined")
    max_ltv_insured: Decimal = Field(..., ge=0, le=95, description="Maximum LTV for insured mortgages")
    max_ltv_conventional: Decimal = Field(..., ge=0, le=80, description="Maximum LTV for conventional mortgages")
    max_amortization_insured: int = Field(..., ge=1, le=30, description="Max amortization period for insured loans")
    max_amortization_conventional: int = Field(..., ge=1, le=30, description="Max amortization period for conventional loans")
    min_credit_score: int = Field(..., ge=300, le=900, description="Minimum acceptable credit score")
    max_gds: Decimal = Field(..., ge=0, le=100, description="Maximum Gross Debt Service ratio allowed")
    max_tds: Decimal = Field(..., ge=0, le=100, description="Maximum Total Debt Service ratio allowed")
    allows_self_employed: bool = Field(False, description="Whether self-employed applicants are accepted")
    allows_rental_income: bool = Field(False, description="Whether rental income can be used")
    allows_gifted_down_payment: bool = Field(False, description="Whether gifted down payments are accepted")
    prepayment_privilege_percent: Optional[Decimal] = Field(None, ge=0, le=100, description="Percentage of principal that can be prepaid annually")
    portability: bool = Field(False, description="Whether the loan is portable")
    assumability: bool = Field(False, description="Whether the loan is assumable")
    is_active: bool = Field(True, description="Whether the product is currently available")
    effective_date: datetime = Field(..., description="When this product becomes effective")
    expiry_date: Optional[datetime] = Field(None, description="When this product expires")

    @validator('term_years')
    def validate_term_for_heloc(cls, v, values):
        if values.get('mortgage_type') == MortgageType.HELOC and v is not None:
            raise ValueError('HELOC products should not have a term_years value')
        return v


class LenderProductUpdateRequest(LenderProductCreateRequest):
    pass


class LenderSubmissionCreateRequest(BaseModel):
    application_id: int = Field(..., gt=0, description="ID of the application being submitted")
    lender_id: int = Field(..., gt=0, description="ID of the target lender")
    product_id: int = Field(..., gt=0, description="ID of the specific product")
    submitted_by: int = Field(..., gt=0, description="User ID who submitted")
    lender_reference_number: Optional[str] = Field(None, max_length=100, description="Reference number from lender")
    lender_conditions: Optional[str] = Field(None, description="Conditions provided by lender")
    approved_rate: Optional[Decimal] = Field(None, description="Approved interest rate")
    approved_amount: Optional[Decimal] = Field(None, description="Approved loan amount")
    expiry_date: Optional[date] = Field(None, description="Date when approval expires")
    notes: Optional[str] = Field(None, description="Internal notes about submission")


class LenderSubmissionUpdateRequest(BaseModel):
    status: SubmissionStatus = Field(..., description="New status of the submission")
    approved_rate: Optional[Decimal] = Field(None, description="Updated approved interest rate")
    approved_amount: Optional[Decimal] = Field(None, description="Updated approved loan amount")
    expiry_date: Optional[date] = Field(None, description="Updated expiry date")
    notes: Optional[str] = Field(None, description="Updated internal notes")


class LenderMatchRequest(BaseModel):
    application_id: int = Field(..., gt=0, description="Application ID to match against lenders")
    ltv_ratio: Decimal = Field(..., description="Loan-to-value ratio")
    gds_ratio: Decimal = Field(..., description="Gross Debt Service ratio")
    tds_ratio: Decimal = Field(..., description="Total Debt Service ratio")
    credit_score: int = Field(..., ge=300, le=900, description="Applicant's credit score")
    is_self_employed: bool = Field(False, description="Whether applicant is self-employed")
    has_rental_income: bool = Field(False, description="Whether applicant has rental income")
    gifted_down_payment: bool = Field(False, description="Whether using a gifted down payment")


# Response Schemas
class LenderResponse(BaseModel):
    id: int
    name: str
    type: LenderType
    is_active: bool
    logo_url: Optional[str]
    submission_email: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class LenderProductResponse(BaseModel):
    id: int
    lender_id: int
    product_name: str
    mortgage_type: MortgageType
    term_years: Optional[int]
    rate: Decimal
    rate_type: RateType
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
    prepayment_privilege_percent: Optional[Decimal]
    portability: bool
    assumability: bool
    is_active: bool
    effective_date: datetime
    expiry_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class LenderSubmissionResponse(BaseModel):
    id: int
    application_id: int
    lender_id: int
    product_id: int
    submitted_by: int
    submitted_at: datetime
    status: SubmissionStatus
    lender_reference_number: Optional[str]
    lender_conditions: Optional[str]
    approved_rate: Optional[Decimal]
    approved_amount: Optional[Decimal]
    expiry_date: Optional[date]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class MatchResultResponse(BaseModel):
    product_id: int
    lender_id: int
    product_name: str
    lender_name: str
    rate: Decimal
    term_years: Optional[int]
    max_ltv_insured: Decimal
    max_ltv_conventional: Decimal
    max_amortization_insured: int
    max_amortization_conventional: int
    flags: List[str] = Field(default_factory=list, description="Special conditions or limitations")


class LenderWithProductsResponse(LenderResponse):
    products: List[LenderProductResponse] = []


class ApplicationMatchesResponse(BaseModel):
    matches: List[MatchResultResponse]


class SubmissionsListResponse(BaseModel):
    submissions: List[LenderSubmissionResponse]
```