from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime
from typing import Optional


class MortgageApplicationBase(BaseModel):
    client_id: int = Field(..., description="FK to clients table")
    purchase_price: Decimal = Field(..., gt=0, description="Property purchase price in CAD")
    down_payment: Decimal = Field(..., gt=0, description="Down payment amount in CAD")
    interest_rate: Decimal = Field(..., ge=0, description="Contract interest rate as percentage")
    property_value: Decimal = Field(..., gt=0, description="Appraised property value in CAD")
    amortization_period: int = Field(..., gt=0, le=30, description="Amortization period in years")


class MortgageApplicationCreate(MortgageApplicationBase):
    pass


class MortgageApplicationUpdate(BaseModel):
    purchase_price: Optional[Decimal] = Field(None, gt=0)
    down_payment: Optional[Decimal] = Field(None, gt=0)
    interest_rate: Optional[Decimal] = Field(None, ge=0)
    property_value: Optional[Decimal] = Field(None, gt=0)
    amortization_period: Optional[int] = Field(None, gt=0, le=30)


class MortgageApplicationResponse(MortgageApplicationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class GDSCalculationRequest(BaseModel):
    gross_income: Decimal = Field(..., gt=0)
    monthly_debt_payments: Decimal = Field(..., ge=0)
    property_taxes: Decimal = Field(..., ge=0)
    heating_costs: Decimal = Field(..., ge=0)
    condo_fees: Decimal = Field(0, ge=0)
    interest_rate: Decimal = Field(..., ge=0)


class TDSCalculationRequest(GDSCalculationRequest):
    pass


class RatioCalculationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    gds_ratio: Decimal
    tds_ratio: Decimal
    qualifying_rate: Decimal
    gds_limit_met: bool
    tds_limit_met: bool
    calculation_breakdown: dict


class InsuranceEligibilityRequest(BaseModel):
    loan_amount: Decimal = Field(..., gt=0)
    property_value: Decimal = Field(..., gt=0)


class InsuranceEligibilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    insurance_required: bool
    ltv_ratio: Decimal
    premium_percentage: Optional[Decimal] = None
    premium_amount: Optional[Decimal] = None