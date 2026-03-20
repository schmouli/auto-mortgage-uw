from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List

from pydantic import BaseModel, Field, ConfigDict


class PolicyLimits(BaseModel):
    ltv_max_insured: Decimal = Field(..., gt=0, le=95)
    ltv_max_conventional: Decimal = Field(..., gt=0, le=80)
    gds_max: Decimal = Field(..., ge=0, le=100)
    tds_max: Decimal = Field(..., ge=0, le=100)
    credit_score_min: int = Field(..., ge=300, le=900)
    amortization_max_insured: int = Field(..., gt=0, le=30)
    amortization_max_conventional: int = Field(..., gt=0, le=35)
    allowed_property_types: List[str] = Field(...)
    excluded_property_types: List[str] = Field(default_factory=list)


class LenderPolicyCreate(BaseModel):
    lender_id: str = Field(..., min_length=1, max_length=50)
    xml_content: str = Field(..., min_length=100)


class LenderPolicyUpdate(BaseModel):
    xml_content: str = Field(..., min_length=100)


class LenderPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    lender_id: str
    version: str


class PolicyEvaluateRequest(BaseModel):
    application_id: int = Field(..., gt=0)
    lender_id: str = Field(..., min_length=1)
    applicant_data: Dict[str, Any] = Field(...)
    property_data: Dict[str, Any] = Field(...)
    loan_data: Dict[str, Any] = Field(...)


class PolicyEvaluateResponse(BaseModel):
    passed: bool
    details: Dict[str, Any]
    policy_limits: PolicyLimits


class PolicyListResponse(BaseModel):
    items: List[LenderPolicyResponse]
    total: int
    page: int
    size: int