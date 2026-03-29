from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_validator


class ClientBase(BaseModel):
    employment_status: str = Field(..., min_length=1, max_length=100)
    employer_name: Optional[str] = Field(None, max_length=255)
    years_employed: int = Field(..., ge=0)
    annual_income: Decimal = Field(..., gt=0)
    other_income: Decimal = Field(0, ge=0)
    credit_score: int = Field(..., ge=300, le=900)
    marital_status: str = Field(..., min_length=1, max_length=50)


class ClientCreate(ClientBase):
    sin: str = Field(..., min_length=9, max_length=9, description="Social Insurance Number")
    date_of_birth: str = Field(..., description="Date of birth in YYYY-MM-DD format")


class ClientUpdate(ClientBase):
    pass


class ClientResponse(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class CoBorrowerBase(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    annual_income: Decimal = Field(..., gt=0)
    employment_status: str = Field(..., min_length=1, max_length=100)
    credit_score: int = Field(..., ge=300, le=900)


class CoBorrowerCreate(CoBorrowerBase):
    sin: str = Field(..., min_length=9, max_length=9, description="Social Insurance Number")


class CoBorrowerUpdate(CoBorrowerBase):
    pass


class CoBorrowerResponse(CoBorrowerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    application_id: int
    created_at: datetime
    updated_at: datetime


class MortgageApplicationBase(BaseModel):
    application_type: str = Field(..., pattern="^(purchase|refinance)$")
    property_address: str = Field(..., min_length=1)
    property_type: str = Field(..., min_length=1, max_length=100)
    property_value: Decimal = Field(..., gt=0)
    purchase_price: Decimal = Field(..., gt=0)
    down_payment: Decimal = Field(..., ge=0)
    requested_loan_amount: Decimal = Field(..., gt=0)
    amortization_years: int = Field(..., ge=5, le=30)
    term_years: int = Field(..., ge=1, le=10)
    mortgage_type: str = Field(..., pattern="^(fixed|variable|adjustable)$")

    @field_validator('down_payment')
    def validate_down_payment(cls, v, info):
        if 'purchase_price' in info.data and v > info.data['purchase_price']:
            raise ValueError('Down payment cannot exceed purchase price')
        return v


class MortgageApplicationCreate(MortgageApplicationBase):
    pass


class MortgageApplicationUpdate(MortgageApplicationBase):
    status: Optional[str] = Field(None, pattern="^(draft|submitted|under_review|approved|denied)$")


class MortgageApplicationResponse(MortgageApplicationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    broker_id: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]


class ApplicationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client: ClientResponse
    application: MortgageApplicationResponse
    co_borrowers: List[CoBorrowerResponse]