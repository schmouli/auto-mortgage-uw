```python
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime
from typing import Optional


class ClientBase(BaseModel):
    first_name: str = Field(..., max_length=50)
    last_name: str = Field(..., max_length=50)
    email: str = Field(..., max_length=255)
    phone: Optional[str] = Field(None, max_length=20)


class ClientCreate(ClientBase):
    pass


class ClientResponse(ClientBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class ApplicationBase(BaseModel):
    client_id: int = Field(..., gt=0)
    property_value: Decimal = Field(..., gt=0)
    down_payment: Decimal = Field(..., ge=0)
    loan_amount: Decimal = Field(..., gt=0)  # Matches DB constraint
    interest_rate: Decimal = Field(..., ge=0)
    amortization_years: int = Field(..., gt=0, le=30)


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdate(BaseModel):
    property_value: Optional[Decimal] = Field(None, gt=0)
    down_payment: Optional[Decimal] = Field(None, ge=0)
    loan_amount: Optional[Decimal] = Field(None, gt=0)
    interest_rate: Optional[Decimal] = Field(None, ge=0)
    amortization_years: Optional[int] = Field(None, gt=0, le=30)


class ApplicationResponse(ApplicationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
```