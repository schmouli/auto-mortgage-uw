from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator

# Request Schemas

class DebtItem(BaseModel):
    debt_type: str = Field(..., max_length=50, description="Type of debt (e.g., credit_card, car_loan)")
    monthly_payment: Decimal = Field(..., gt=0, description="Monthly payment amount")
    balance: Optional[Decimal] = Field(None, ge=0, description="Outstanding balance")
    is_secured: Optional[bool] = Field(False, description="Whether the debt is secured")


class UnderwritingCalculationRequest(BaseModel):
    property_value: Decimal = Field(..., gt=0, description="Property value in CAD")
    loan_amount: Decimal = Field(..., gt=0, description="Requested loan amount in CAD")
    contract_rate: Decimal = Field(..., gt=0, description="Contract interest rate as decimal (e.g., 0.0525 for 5.25%)")
    gross_monthly_income: Decimal = Field(..., gt=0, description="Total gross monthly income in CAD")
    monthly_property_tax: Decimal = Field(..., ge=0, description="Monthly property tax expense in CAD")
    monthly_heating: Decimal = Field(..., ge=0, description="Monthly heating cost in CAD")
    monthly_condo_fees: Decimal = Field(Decimal('0.00'), ge=0, description="Monthly condominium fees in CAD")
    other_monthly_debts: List[DebtItem] = Field(default_factory=list, description="List of other monthly debt obligations")
    rental_income: Decimal = Field(Decimal('0.00'), ge=0, description="Rental income in CAD (if applicable)")
    rental_property_expenses: Decimal = Field(Decimal('0.00'), ge=0, description="Expenses related to rental property in CAD")
    is_self_employed: bool = Field(False, description="Flag indicating if applicant is self-employed")
    self_employed_income_verified: bool = Field(False, description="Whether self-employed income has been verified")
    down_payment_amount: Decimal = Field(..., ge=0, description="Down payment amount in CAD")
    amortization_years: int = Field(25, ge=5, le=30, description="Amortization period in years (5-30)")

    @field_validator('loan_amount')
    def validate_loan_vs_property(cls, v, info):
        property_value = info.data.get('property_value')
        if property_value and v > property_value:
            raise ValueError('Loan amount cannot exceed property value')
        return v


class UnderwritingEvaluationRequest(UnderwritingCalculationRequest):
    client_id: int = Field(..., gt=0, description="ID of the client being evaluated")
    application_id: Optional[int] = Field(None, gt=0, description="ID of the mortgage application (optional)")


class OverrideRequest(BaseModel):
    reason: str = Field(..., min_length=10, max_length=1000, description="Reason for override")
    new_decision: Literal["APPROVED", "CONDITIONAL", "DECLINED"] = Field(..., description="New underwriting decision")


# Response Schemas

class DeclineReasonSchema(BaseModel):
    code: str = Field(..., description="Machine-readable decline reason code")
    message: str = Field(..., description="Human-readable decline reason message")


class ConditionSchema(BaseModel):
    code: str = Field(..., description="Machine-readable condition code")
    message: str = Field(..., description="Human-readable condition message")


class UnderwritingCalculationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    qualifies: bool
    decision: Literal["APPROVED", "CONDITIONAL", "DECLINED"]
    gds_ratio: Decimal  # e.g., 0.35 for 35%
    tds_ratio: Decimal
    ltv_ratio: Decimal
    cmhc_required: bool
    cmhc_premium_amount: Optional[Decimal]
    qualifying_rate: Decimal
    max_mortgage_amount: Decimal
    decline_reasons: List[DeclineReasonSchema]
    conditions: List[ConditionSchema]
    stress_test_passed: bool


class UnderwritingResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    client_id: int
    application_id: Optional[int]
    
    # Ratios and Calculations
    gds_ratio: Decimal
    tds_ratio: Decimal
    ltv_ratio: Decimal
    qualifying_rate: Decimal
    max_mortgage_amount: Decimal
    
    # CMHC Insurance
    cmhc_required: bool
    cmhc_premium_amount: Optional[Decimal]
    
    # Decision
    qualifies: bool
    decision: str
    decline_reasons: Optional[str]  # JSON array of reasons
    conditions: Optional[str]  # JSON array of conditions
    stress_test_passed: bool
    
    # Metadata
    created_at: datetime
    created_by: Optional[int]


class OverrideResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    underwriting_result_id: int
    overridden_by: int
    reason: str
    previous_decision: str
    new_decision: str
    created_at: datetime