from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime


class ApplicationCreate(BaseModel):
    client_id: int = Field(..., description="FK to clients table")
    purchase_price: Decimal = Field(..., gt=0, description="Property purchase price in CAD", le=100000000)  # FIXED: Added upper limit


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    purchase_price: Decimal
    created_at: datetime