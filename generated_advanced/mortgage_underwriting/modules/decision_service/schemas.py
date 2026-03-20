from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class EmploymentType(str, Enum):
    salaried = "salaried"
    self_employed = "self_employed"
    contract = "contract"


class PropertyType(str, Enum):
    single_family = "single_family"
    condo = "condo"
    townhouse = "townhouse"
    multi_unit = "multi_unit"


class DecisionEvaluateRequest(BaseModel):
    application_id: UUID = Field(..., description="Reference to application in Application module")
    policy_version: str = Field("v1.2024", description="Policy rule version to apply")
    
    class BorrowerProfileDTO(BaseModel):
        gross_annual_income: Decimal = Field(..., gt=0, description="Must be pre-validated income")
        monthly_debt_obligations: Decimal = Field(0, ge=0, description="Sum of all non-housing debt payments")
        credit_score: int = Field(..., ge=300, le=900)
        employment_type: EmploymentType
        is_first_time_homebuyer: bool = False
        
    class PropertyDetailsDTO(BaseModel):
        property_value: Decimal = Field(..., gt=0, description="Appraised property value")
        property_type: PropertyType
        property_tax_annual: Decimal = Field(..., ge=0)
        
    class LoanDetailsDTO(BaseModel):
        requested_amount: Decimal = Field(..., gt=0)
        amortization_years: int = Field(..., ge=5, le=30, description="5-30 years")
        contract_rate: Decimal = Field(..., ge=0, description="Annual interest rate")
        is_insured: bool = False
        down_payment_amount: Decimal = Field(..., gt=0)
    
    borrower_profile: BorrowerProfileDTO
    property_details: PropertyDetailsDTO
    loan_details: LoanDetailsDTO


class DecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    application_id: UUID
    decision: str  # approved, declined, exception
    confidence_score: Decimal = Field(..., ge=0, le=1)
    
    class RatioBreakdownDTO(BaseModel):
        gds: Decimal
        tds: Decimal
        ltv: Decimal
        
    ratios: RatioBreakdownDTO
    cmhc_required: bool
    stress_test_rate: Decimal
    policy_flags: List[str]
    exceptions: List[Dict[str, Any]]
    audit_trail: Dict[str, Any]
    
    created_at: datetime


class DecisionRetrieveResponse(DecisionResponse):
    pass


class AuditTrailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    step: str
    details: Dict[str, Any]
    timestamp: datetime


class DecisionListResponse(BaseModel):
    items: List[DecisionRetrieveResponse]
    total: int
    page: int
    size: int