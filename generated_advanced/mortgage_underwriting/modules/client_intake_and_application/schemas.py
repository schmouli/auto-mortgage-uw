from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, validator

# --- Client Schemas ---


class ClientBase(BaseModel):
    employment_status: Optional[str] = Field(None, max_length=100)
    employer_name: Optional[str] = Field(None, max_length=255)
    years_employed: Optional[int] = Field(None, ge=0)
    annual_income: Decimal = Field(..., gt=0)
    other_income: Optional[Decimal] = Field(None, ge=0)
    credit_score: Optional[int] = Field(None, ge=300, le=900)
    marital_status: Optional[str] = Field(None, max_length=50)


class ClientCreate(ClientBase):
    user_id: int
    # Note: SIN and DOB are handled separately for security - not included in regular create


class ClientUpdate(ClientBase):
    pass


class ClientResponse(ClientBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    # Security: Excluded sensitive fields from response


class ClientCreateWithPII(ClientCreate):
    """Special schema for creating client with PII - should only be used internally or with proper authz"""
    sin_raw: Optional[str] = Field(None, description="Raw SIN - will be encrypted")
    date_of_birth_raw: Optional[str] = Field(None, description="Raw DOB - will be encrypted")


class ClientUpdateWithPII(ClientUpdate):
    """Special schema for updating client with PII - should only be used internally or with proper authz"""
    sin_raw: Optional[str] = Field(None, description="Raw SIN - will be encrypted")
    date_of_birth_raw: Optional[str] = Field(None, description="Raw DOB - will be encrypted")


# --- Co-Borrower Schemas ---


class CoBorrowerBase(BaseModel):
    full_name: str = Field(..., max_length=255)
    annual_income: Decimal = Field(..., gt=0)
    employment_status: Optional[str] = Field(None, max_length=100)
    credit_score: Optional[int] = Field(None, ge=300, le=900)


class CoBorrowerCreate(CoBorrowerBase):
    # Note: SIN is handled separately for security - not included in regular create
    pass


class CoBorrowerCreateWithPII(CoBorrowerCreate):
    """Special schema for creating co-borrower with PII - should only be used internally or with proper authz"""
    sin_raw: Optional[str] = Field(None, description="Raw SIN - will be encrypted")


class CoBorrowerUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    annual_income: Optional[Decimal] = Field(None, gt=0)
    employment_status: Optional[str] = Field(None, max_length=100)
    credit_score: Optional[int] = Field(None, ge=300, le=900)


class CoBorrowerUpdateWithPII(CoBorrowerUpdate):
    """Special schema for updating co-borrower with PII - should only be used internally or with proper authz"""
    sin_raw: Optional[str] = Field(None, description="Raw SIN - will be encrypted")


class CoBorrowerResponse(CoBorrowerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    created_at: datetime
    updated_at: datetime
    # Security: Excluded sensitive fields from response


# --- Application Schemas ---


class MortgageApplicationBase(BaseModel):
    client_id: int
    property_address: str = Field(..., max_length=1000)
    property_type: str = Field(..., pattern="^(single_family|condo|townhouse|multi_unit|rural)$")
    property_value: Decimal = Field(..., gt=0)
    purchase_price: Decimal = Field(..., gt=0)
    down_payment: Decimal = Field(..., ge=0)
    requested_loan_amount: Decimal = Field(..., ge=0)
    amortization_years: int = Field(..., ge=5, le=30)
    term_years: int = Field(..., ge=1, le=10)
    mortgage_type: str = Field(..., pattern="^(fixed|variable)$")
    co_borrowers: Optional[List[CoBorrowerCreate]] = None

    @validator('purchase_price')
    def purchase_price_not_exceed_value(cls, v, values, **kwargs):
        if 'property_value' in values and v > values['property_value']:
            raise ValueError('Purchase price cannot exceed property value')
        return v

    @validator('requested_loan_amount')
    def loan_equals_purchase_minus_down(cls, v, values, **kwargs):
        if 'purchase_price' in values and 'down_payment' in values:
            expected = values['purchase_price'] - values['down_payment']
            if abs(v - expected) > Decimal('0.01'):  # Allow small rounding differences
                raise ValueError('Requested loan amount must equal purchase price minus down payment')
        return v


class MortgageApplicationCreate(MortgageApplicationBase):
    pass


class MortgageApplicationUpdate(BaseModel):
    property_address: Optional[str] = Field(None, max_length=1000)
    property_type: Optional[str] = Field(None, pattern="^(single_family|condo|townhouse|multi_unit|rural)$")
    property_value: Optional[Decimal] = Field(None, gt=0)
    purchase_price: Optional[Decimal] = Field(None, gt=0)
    down_payment: Optional[Decimal] = Field(None, ge=0)
    requested_loan_amount: Optional[Decimal] = Field(None, ge=0)
    amortization_years: Optional[int] = Field(None, ge=5, le=30)
    term_years: Optional[int] = Field(None, ge=1, le=10)
    mortgage_type: Optional[str] = Field(None, pattern="^(fixed|variable)$")


class MortgageApplicationResponse(MortgageApplicationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    broker_id: Optional[int]
    application_type: str
    status: str
    ltv_ratio: Optional[Decimal]
    gds_ratio: Optional[Decimal]
    tds_ratio: Optional[Decimal]
    insurance_required: Optional[bool]
    insurance_premium_rate: Optional[Decimal]
    submitted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    co_borrowers: List[CoBorrowerResponse] = []


class ApplicationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_full_name: str
    property_address: str
    property_value: Decimal
    purchase_price: Decimal
    down_payment: Decimal
    requested_loan_amount: Decimal
    ltv_ratio: Optional[Decimal]
    gds_ratio: Optional[Decimal]
    tds_ratio: Optional[Decimal]
    insurance_required: Optional[bool]
    insurance_premium_rate: Optional[Decimal]
    submitted_at: Optional[datetime]