from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

class ClientBase(BaseModel):
    employment_status: str = Field(..., max_length=50)
    employer_name: Optional[str] = Field(None, max_length=255)
    years_employed: int = Field(default=0, ge=0)
    annual_income: Decimal = Field(..., gt=0)
    other_income: Decimal = Field(default=Decimal('0.00'), ge=0)
    credit_score: int = Field(..., ge=300, le=900)
    marital_status: str = Field(..., max_length=20)


class ClientCreate(ClientBase):
    sin: str = Field(..., min_length=9, max_length=9, pattern=r"^\d{9}$")
    date_of_birth: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD


class ClientUpdate(ClientBase):
    pass


class ClientResponse(ClientBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    created_at: datetime


class CoBorrowerBase(BaseModel):
    full_name: str = Field(..., max_length=255)
    sin: str = Field(..., min_length=9, max_length=9, pattern=r"^\d{9}$")
    annual_income: Decimal = Field(..., gt=0)
    employment_status: str = Field(..., max_length=50)
    credit_score: int = Field(..., ge=300, le=900)


class CoBorrowerCreate(CoBorrowerBase):
    pass


class CoBorrowerResponse(CoBorrowerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ApplicationBase(BaseModel):
    property_address: str
    property_type: Literal['single_family', 'condo', 'townhouse', 'duplex']
    property_value: Optional[Decimal] = Field(None, gt=0)
    purchase_price: Optional[Decimal] = Field(None, gt=0)
    down_payment: Decimal = Field(..., gt=0)
    requested_loan_amount: Decimal = Field(..., gt=0)
    amortization_years: int = Field(..., ge=5, le=30)
    term_years: int = Field(..., ge=1, le=10)
    mortgage_type: Literal['fixed', 'variable']
    application_type: Literal['purchase', 'refinance', 'renewal']

    @field_validator('purchase_price')
    def validate_purchase_price(cls, v: Optional[Decimal], info) -> Optional[Decimal]:
        if info.data.get('application_type') == 'purchase' and v is None:
            raise ValueError('purchase_price is required for purchase applications')
        return v

    @field_validator('property_value')
    def validate_property_value(cls, v: Optional[Decimal], info) -> Optional[Decimal]:
        if info.data.get('application_type') in ['refinance', 'renewal'] and v is None:
            raise ValueError('property_value is required for refinance/renewal applications')
        return v


class ApplicationCreate(ApplicationBase):
    client_id: Optional[int] = Field(None, description="Required for brokers; inferred for clients")
    co_borrowers: Optional[List[CoBorrowerCreate]] = None


class ApplicationUpdate(ApplicationBase):
    pass


class ApplicationResponse(ApplicationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    broker_id: Optional[int]
    status: str
    ltv_ratio: Optional[Decimal]
    insurance_required: bool
    cmhc_premium_rate: Optional[Decimal]
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]


class ApplicationSummaryResponse(ApplicationResponse):
    """Extended response including calculated fields for PDF generation."""
    total_income: Decimal
    gds_ratio: Decimal
    tds_ratio: Decimal
    qualifying_rate: Decimal