from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class UnderwritingCalculateRequest(BaseModel):
    client_id: int = Field(..., description="FK to clients table")
    property_value: Decimal = Field(..., gt=0, description="Property market value in CAD")
    down_payment: Decimal = Field(..., ge=0, description="Down payment amount in CAD")
    annual_property_tax: Decimal = Field(..., ge=0, description="Annual property tax in CAD")
    monthly_heating_cost: Decimal = Field(..., ge=0, description="Monthly heating cost in CAD")
    monthly_condo_fees: Decimal = Field(0, ge=0, description="Monthly condo fees in CAD")
    gross_monthly_income: Decimal = Field(..., gt=0, description="Total gross monthly income in CAD")
    total_monthly_debts: Decimal = Field(0, ge=0, description="Total monthly debt obligations in CAD")
    contract_rate: Decimal = Field(..., ge=0, description="Contract interest rate as percentage (e.g., 5.25 for 5.25%)")


class UnderwritingResultBase(BaseModel):
    qualifies: bool
    decision: str = Field(pattern="^(APPROVED|CONDITIONAL|DECLINED)$")
    gds_ratio: Decimal = Field(..., ge=0, le=100)
    tds_ratio: Decimal = Field(..., ge=0, le=100)
    ltv_ratio: Decimal = Field(..., ge=0, le=100)
    cmhc_required: bool
    cmhc_premium_amount: Optional[Decimal] = Field(None, ge=0)
    qualifying_rate: Decimal = Field(..., ge=0)
    max_mortgage: Decimal = Field(..., ge=0)
    stress_test_passed: bool
    decline_reasons: Optional[str] = None
    conditions: Optional[str] = None


class UnderwritingResultCreate(UnderwritingResultBase):
    application_id: int
    client_id: int


class UnderwritingResultUpdate(BaseModel):
    override_reason: str = Field(..., min_length=10, max_length=500)


class UnderwritingResultResponse(UnderwritingResultBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    client_id: int
    override_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime