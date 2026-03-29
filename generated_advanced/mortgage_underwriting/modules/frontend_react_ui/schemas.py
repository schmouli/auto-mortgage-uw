from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime

class ApplicationCreate(BaseModel):
    client_id: int = Field(..., description="FK to clients table")
    purchase_price: Decimal = Field(..., gt=0, description="Property purchase price in CAD")  # FIXED: Use Decimal type hint

class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    purchase_price: Decimal  # FIXED: Use Decimal type hint
    created_at: datetime  # FIXED: Include timestamp field in schema