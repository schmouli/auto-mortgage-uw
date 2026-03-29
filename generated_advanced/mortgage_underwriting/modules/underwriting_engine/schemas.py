from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class UnderwritingCalculationRequest(BaseModel):
    """Request schema for underwriting calculation (no save)."""
    
    # Property
    purchase_price: Decimal = Field(..., gt=0, description="Property purchase price in CAD")
    down_payment: Decimal = Field(..., gt=0, description="Down payment amount in CAD")
    
    # Rates
    contract_rate: Decimal = Field(..., gt=0, description="Contract interest rate as percentage (e.g., 5.5 for 5.5%)")
    
    # Applicant Info
    gross_monthly_income: Decimal = Field(..., gt=0, description="Total gross monthly income in CAD")
    monthly_debts: Decimal = Field(0, ge=0, description="Total monthly debt obligations in CAD")
    condo_fees: Decimal = Field(0, ge=0, description="Monthly condominium fees in CAD")
    
    # Validation
    @property
    def loan_amount(self) -> Decimal:
        return self.purchase_price - self.down_payment
    
    @property
    def ltv_ratio(self) -> Decimal:
        if self.purchase_price <= 0:
            return Decimal('0')
        return (self.loan_amount / self.purchase_price) * 100


class UnderwritingEvaluationRequest(UnderwritingCalculationRequest):
    """Request schema for underwriting evaluation (with save)."""
    application_id: int = Field(..., gt=0, description="FK to mortgage_applications table")
    client_id: int = Field(..., gt=0, description="FK to clients table")


class UnderwritingOverrideRequest(BaseModel):
    """Request schema for admin override."""
    reason: str = Field(..., min_length=10, max_length=1000, description="Reason for override")


class UnderwritingResultResponse(BaseModel):
    """Complete underwriting result response."""
    model_config = ConfigDict(from_attributes=True)
    
    # Ratios
    gds_ratio: Decimal
    tds_ratio: Decimal
    ltv_ratio: Decimal
    
    # Qualification
    qualifies: bool
    decision: str  # APPROVED, CONDITIONAL, DECLINED
    
    # Financials
    qualifying_rate: Decimal
    max_mortgage: Decimal
    
    # Insurance
    cmhc_required: bool
    cmhc_premium_amount: Optional[Decimal]
    cmhc_premium_percent: Optional[Decimal]
    
    # Metadata
    decline_reasons: Optional[List[str]]
    conditions: Optional[List[str]]
    stress_test_passed: bool


class UnderwritingCalculationResponse(BaseModel):
    """Underwriting calculation response without persistence."""
    model_config = ConfigDict(from_attributes=True)
    
    # Ratios
    gds_ratio: Decimal
    tds_ratio: Decimal
    ltv_ratio: Decimal
    
    # Qualification
    qualifies: bool
    decision: str  # APPROVED, CONDITIONAL, DECLINED
    
    # Financials
    qualifying_rate: Decimal
    max_mortgage: Decimal
    
    # Insurance
    cmhc_required: bool
    cmhc_premium_amount: Optional[Decimal]
    cmhc_premium_percent: Optional[Decimal]
    
    # Metadata
    decline_reasons: Optional[List[str]]
    conditions: Optional[List[str]]
    stress_test_passed: bool


class UnderwritingOverrideResponse(BaseModel):
    """Admin override response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    result_id: int
    admin_user_id: int
    reason: str
    created_at: datetime