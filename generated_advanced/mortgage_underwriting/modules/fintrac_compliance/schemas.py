from pydantic import BaseModel, Field, ConfigDict, field_validator
from decimal import Decimal
from datetime import datetime

class ApplicationCreate(BaseModel):
    client_id: int = Field(..., description="FK to clients table")
    purchase_price: Decimal = Field(..., gt=0, description="Property purchase price in CAD")

    @field_validator('purchase_price')
    @classmethod
    def validate_purchase_price(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError('Purchase price must be greater than zero')
        return v

class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    purchase_price: Decimal
    created_at: datetime