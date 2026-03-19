from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator

# Input Schemas


class UnderwritingCalculationRequest(BaseModel):
    property_value: Decimal = Field(..., gt=0, description="Property value in CAD")
    loan_amount: Decimal = Field(..., gt=0, description="Requested loan amount in CAD")
    contract_rate: Decimal = Field(..., gt=0, description="Contract interest rate as decimal (e.g., 0.0595)")
    amortization_years: int = Field(..., ge=5, le=30, description="Amortization period in years (5-30)")
    property_type: Literal["single_family", "condo", "multi_unit"] = Field(..., description="Type of property")
    condo_fees_monthly: Optional[Decimal] = Field(None, ge=0, description="Monthly condo fees if applicable")
    gross_monthly_income: Decimal = Field(..., gt=0, description="Total gross monthly income in CAD")
    monthly_debt_payments: Decimal = Field(..., ge=0, description="Total monthly debt payments in CAD")
    property_taxes_annual: Decimal = Field(..., ge=0, description="Annual property taxes in CAD")
    heating_costs_monthly: Decimal = Field(..., gt=0, description="Monthly heating costs in CAD")
    down_payment_amount: Decimal = Field(..., gt=0, description="Down payment amount in CAD")

    @field_validator('condo_fees_monthly')
    def validate_condo_fees(cls, v: Optional[Decimal]) -> Decimal:
        return v or Decimal('0.00')


class UnderwritingEvaluationRequest(UnderwritingCalculationRequest):
    application_id: int = Field(..., gt=0, description="Application ID to associate with result")

# Output Schemas


class UnderwritingResultBase(BaseModel):
    qualifies: bool
    decision: Literal["APPROVED", "CONDITIONAL", "DECLINED"]
    gds_ratio: Decimal = Field(..., max_digits=5, decimal_places=4)
    tds_ratio: Decimal = Field(..., max_digits=5, decimal_places=4)
    ltv_ratio: Decimal = Field(..., max_digits=5, decimal_places=4)
    cmhc_required: bool
    cmhc_premium_amount: Decimal = Field(..., max_digits=15, decimal_places=2)
    qualifying_rate: Decimal = Field(..., max_digits=5, decimal_places=4)
    max_mortgage: Decimal = Field(..., max_digits=15, decimal_places=2)
    decline_reasons: Optional[List[str]] = None
    conditions: Optional[List[str]] = None
    stress_test_passed: bool

    model_config = ConfigDict(from_attributes=True)


class UnderwritingResultCreate(UnderwritingResultBase):
    application_id: int


class UnderwritingResultResponse(UnderwritingResultBase):
    id: int
    application_id: int
    created_at: datetime
    updated_at: datetime


class UnderwritingOverrideCreate(BaseModel):
    result_id: int = Field(..., gt=0)
    reason: str = Field(..., min_length=10, max_length=1000)
    approved: bool


class UnderwritingOverrideResponse(BaseModel):
    id: int
    result_id: int
    created_by: Optional[int]
    reason: str
    approved: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)