from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

class BorrowerData(BaseModel):
    gross_annual_income: Decimal = Field(..., gt=0, description="Pre-validated annual income")
    employment_type: Literal["salaried", "self_employed", "contractor"] = Field(...)
    credit_score: int = Field(..., ge=300, le=900, description="Credit score between 300-900")
    date_of_birth: str = Field(..., description="DOB for age-based rules (encrypted in storage)")  # Using str for transport
    is_first_time_homebuyer: bool = Field(...)


class PropertyData(BaseModel):
    property_value: Decimal = Field(..., gt=0)
    property_type: Literal["single_family", "condo", "multi_unit"] = Field(...)
    street_address: str = Field(..., description="For audit only, not persisted")


class LoanData(BaseModel):
    mortgage_amount: Decimal = Field(..., gt=0)
    contract_rate: Decimal = Field(..., ge=0, description="Annual percentage rate")
    amortization_years: int = Field(..., ge=5, le=30)
    payment_frequency: Literal["monthly", "bi_weekly", "accelerated_bi_weekly"] = Field(...)


class DebtData(BaseModel):
    monthly_payment: Decimal = Field(..., ge=0)
    debt_type: Literal["credit_card", "auto_loan", "student_loan", "other_mortgage"] = Field(...)
    balance: Decimal = Field(..., ge=0)


class DecisionEvaluateRequest(BaseModel):
    application_id: UUID = Field(...)
    borrower_data: BorrowerData = Field(...)
    property_data: PropertyData = Field(...)
    loan_data: LoanData = Field(...)
    existing_debts: List[DebtData] = Field(default_factory=list)
    policy_version: str = Field(default="v1.0", description="Policy rule set version")


class RatioMetrics(BaseModel):
    gds: Decimal = Field(..., description="Gross Debt Service ratio %")
    tds: Decimal = Field(..., description="Total Debt Service ratio %")
    ltv: Decimal = Field(..., description="Loan To Value ratio %")


class DecisionEvaluateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: UUID
    decision: Literal["approved", "declined", "exception"]
    confidence_score: Decimal = Field(..., ge=0, le=1)
    ratios: RatioMetrics
    cmhc_required: bool
    stress_test_rate: Decimal
    policy_flags: List[str]
    exceptions: List[str]
    audit_trail: Dict[str, Any]


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: UUID
    decision: str
    confidence_score: Decimal
    stress_test_rate: Decimal
    cmhc_required: bool
    policy_flags: List[str]
    exceptions: List[str]
    audit_trail: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DecisionAuditTrailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_trail: Dict[str, Any]
    created_at: datetime