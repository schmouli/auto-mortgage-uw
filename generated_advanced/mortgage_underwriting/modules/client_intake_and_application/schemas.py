from pydantic import BaseModel, Field, ConfigDict, field_validator
from decimal import Decimal
from datetime import datetime
from typing import List, Optional


class ClientAddressBase(BaseModel):
    street: str = Field(..., max_length=200)
    city: str = Field(..., max_length=100)
    province: str = Field(..., max_length=50)
    postal_code: str = Field(..., max_length=10)
    country: str = Field(default="Canada", max_length=50)
    is_primary: bool = False


class ClientAddressCreate(ClientAddressBase):
    pass


class ClientAddressUpdate(ClientAddressBase):
    pass


class ClientAddressResponse(ClientAddressBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    created_at: datetime
    updated_at: datetime


class ClientBase(BaseModel):
    first_name: str = Field(..., max_length=50)
    last_name: str = Field(..., max_length=50)
    email: str = Field(..., max_length=100)
    phone: str = Field(..., max_length=20)
    date_of_birth: str = Field(..., description="Date of birth in YYYY-MM-DD format")
    sin: str = Field(..., min_length=9, max_length=9, pattern=r"^\d{9}$")

    @field_validator('date_of_birth')
    def validate_date_of_birth(cls, v):
        # Basic validation - in production, use proper date parsing
        if len(v) != 10 or v[4] != '-' or v[7] != '-':
            raise ValueError('Date of birth must be in YYYY-MM-DD format')
        return v


class ClientCreate(ClientBase):
    addresses: List[ClientAddressCreate] = Field(..., min_items=1)


class ClientUpdate(ClientBase):
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    date_of_birth: Optional[str] = Field(None, description="Date of birth in YYYY-MM-DD format")
    sin: Optional[str] = Field(None, min_length=9, max_length=9, pattern=r"^\d{9}$")
    addresses: Optional[List[ClientAddressUpdate]] = None


class ClientResponse(ClientBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    addresses: List[ClientAddressResponse]
    created_at: datetime
    updated_at: datetime


class MortgageApplicationBase(BaseModel):
    client_id: int = Field(..., gt=0)
    property_value: Decimal = Field(..., gt=0)
    down_payment: Decimal = Field(..., gt=0)
    loan_amount: Decimal = Field(..., gt=0)  # FIXED: Ensure Decimal type
    interest_rate: Decimal = Field(..., ge=0, le=100)
    amortization_period: int = Field(..., ge=1, le=35)


class MortgageApplicationCreate(MortgageApplicationBase):
    pass


class MortgageApplicationUpdate(MortgageApplicationBase):
    client_id: Optional[int] = Field(None, gt=0)
    property_value: Optional[Decimal] = Field(None, gt=0)
    down_payment: Optional[Decimal] = Field(None, gt=0)
    loan_amount: Optional[Decimal] = Field(None, gt=0)
    interest_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    amortization_period: Optional[int] = Field(None, ge=1, le=35)


class MortgageApplicationResponse(MortgageApplicationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime