from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, validator


class BorrowerData(BaseModel):
    gross_annual_income: Decimal = Field(..., gt=0, description="Before-tax income, self-employed handled via 2-year avg")
    monthly_non_housing_debt: Decimal = Field(..., ge=0, description="Sum of credit cards, loans, alimony")
    employment_type: str = Field(..., pattern="^(salaried|self_employed|contractor)$")
    sin_hash: str = Field(..., min_length=64, max_length=64, description="SHA256 hash for PIPEDA compliance")

    @validator('gross_annual_income', 'monthly_non_housing_debt')
    def validate_decimal_precision(cls, v):
        if isinstance(v, Decimal):
            return v.quantize(Decimal('0.01'))
        return v


class PropertyData(BaseModel):
    property_value: Decimal = Field(..., gt=0, description="Market value of the property")
    property_type: str = Field(..., pattern="^(single_family|condo|rental)$")

    @validator('property_value')
    def validate_property_value(cls, v):
        if isinstance(v, Decimal):
            return v.quantize(Decimal('0.01'))
        return v


class LoanData(BaseModel):
    mortgage_amount: Decimal = Field(..., gt=0, description="Requested mortgage amount")
    contract_rate: Decimal = Field(..., ge=0, description="Annual interest rate (e.g., 5.25)")
    amortization_years: int = Field(..., ge=1, le=30, description="Amortization period in years")
    payment_frequency: str = Field(..., pattern="^(monthly|bi_weekly|accelerated_bi_weekly)$")

    @validator('mortgage_amount', 'contract_rate')
    def validate_loan_decimals(cls, v):
        if isinstance(v, Decimal):
            return v.quantize(Decimal('0.01'))
        return v


class DebtItem(BaseModel):
    monthly_payment: Decimal = Field(..., gt=0)
    debt_type: str = Field(..., pattern="^(credit_card|car_loan|student_loan|alimony)$")

    @validator('monthly_payment')
    def validate_payment_amount(cls, v):
        if isinstance(v, Decimal):
            return v.quantize(Decimal('0.01'))
        return v


class DecisionEvaluateRequest(BaseModel):
    application_id: UUID = Field(..., description="Mortgage application UUID")
    borrower_data: BorrowerData
    property_data: PropertyData
    loan_data: LoanData
    existing_debts: List[DebtItem] = Field(default_factory=list)


class RatioBreakdown(BaseModel):
    gds: Decimal = Field(..., description="Gross Debt Service ratio %")
    tds: Decimal = Field(..., description="Total Debt Service ratio %")
    ltv: Decimal = Field(..., description="Loan To Value ratio %")

    @validator('gds', 'tds', 'ltv')
    def validate_ratios(cls, v):
        if isinstance(v, Decimal):
            return v.quantize(Decimal('0.01'))
        return v


class ExceptionItem(BaseModel):
    code: str
    message: str
    severity: str  # error, warning, info


class DecisionEvaluateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    application_id: UUID
    decision: str = Field(..., pattern="^(approved|declined|exception|conditional)$")
    confidence_score: Decimal = Field(..., ge=0, le=1)
    ratios: RatioBreakdown
    cmhc_required: bool
    stress_test_rate: Decimal
    policy_flags: List[str]
    exceptions: List[ExceptionItem]
    audit_trail: Dict[str, Any]  # rules_evaluated, timestamp, model_version


class DecisionRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: UUID
    decision: str
    confidence_score: Decimal
    gds_ratio: Decimal
    tds_ratio: Decimal
    ltv_ratio: Decimal
    cmhc_required: bool
    stress_test_rate: Decimal
    policy_flags: List[str]
    exceptions: List[Dict[str, Any]]
    audit_trail: Dict[str, Any]
    created_at: datetime
    updated_at: datetime