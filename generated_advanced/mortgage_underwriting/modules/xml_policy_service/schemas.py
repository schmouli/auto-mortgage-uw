from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

class LenderPolicyMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lender_id: str = Field(..., max_length=50)
    lender_name: str = Field(..., max_length=255)
    version: str = Field(..., max_length=20)
    is_active: bool
    created_at: datetime
    updated_at: datetime

class LenderPolicyDetail(LenderPolicyMetadata):
    policy_config: Dict[str, Any]

class LenderPolicyListResponse(BaseModel):
    items: List[LenderPolicyMetadata]
    total: int
    page: int
    size: int

class PolicyEvaluationRequest(BaseModel):
    lender_id: str = Field(..., description="Lender identifier")
    applicant_data: Dict[str, Any] = Field(
        ..., description="Applicant information including credit score, income, etc."
    )
    property_data: Dict[str, Any] = Field(
        ..., description="Property details such as value, type, location"
    )
    loan_data: Dict[str, Any] = Field(
        ..., description="Loan parameters like amount, rate, amortization"
    )

class PolicyEvaluationResponse(BaseModel):
    compliant: bool = Field(..., description="Whether application meets policy criteria")
    violations: List[str] = Field(
        ..., description="List of policy rules that were violated, if any"
    )
    details: Optional[Dict[str, Any]] = Field(
        None, description="Detailed breakdown of evaluation results"
    )

class PolicyUpdateRequest(BaseModel):
    xml_content: str = Field(..., description="Full XML policy definition")
    version: str = Field(..., max_length=20, description="New version string")