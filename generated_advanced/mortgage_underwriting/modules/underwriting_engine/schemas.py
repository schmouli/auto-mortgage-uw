```python
from pydantic import BaseModel, Field, validator
from decimal import Decimal
from typing import List, Optional
from datetime import datetime


# Request Schemas
class UnderwritingInputBase(BaseModel):
    gross_monthly_income: Decimal = Field(..., gt=0, description="Gross monthly income")
    property_tax_monthly: Decimal = Field(..., ge=0, description="Monthly property tax")
    heating_cost_monthly: Decimal = Field(..., ge=0, description="Monthly heating cost")
    condo_fee_monthly: Optional[Decimal] = Field(None, ge=0, description="Monthly condo fee if applicable")
    total_debts_monthly: Decimal = Field(..., ge=0, description="Total monthly debt payments")
    property_price: Decimal = Field(..., gt=0, description="Property purchase price")
    down_payment: Decimal = Field(..., gt=0, description="Down payment amount")
    contract_rate: Decimal = Field(..., ge=0, description="Contract interest rate")


class UnderwritingCalculateRequest(UnderwritingInputBase):
    pass


class UnderwritingEvaluateRequest(UnderwritingInputBase):
    changed_by: str = Field(..., min_length=1, max_length=100)


class OverrideCreate(BaseModel):
    overridden_by: str = Field(..., min_length=1, max_length=100)
    reason: str = Field(..., min_length=10, max_length=1000)


# Response Schemas
class DeclineReasonOut(BaseModel):
    reason_code: str
    description: str


class ConditionOut(BaseModel):
    condition_text: str
    is_met: bool


class UnderwritingResultBase(BaseModel):
    qualifies: bool
    decision: str
    gds_ratio: Optional[Decimal]
    tds_ratio: Optional[Decimal]
    ltv_ratio: Optional[Decimal]
    cmhc_required: bool
    cmhc_premium_amount: Optional[Decimal]
    qualifying_rate: Optional[Decimal]
    max_mortgage: Optional[Decimal]
    decline_reasons: List[DeclineReasonOut]
    conditions: List[ConditionOut]
    stress_test_passed: bool


class UnderwritingResultResponse(UnderwritingResultBase):
    id: int
    application_id: str
    created_at: datetime
    updated_at: datetime


class UnderwritingCalculateResponse(UnderwritingResultBase):
    pass
```