from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator


class LenderPolicyBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    lender_id: str = Field(..., max_length=50, description="Unique lender identifier")
    lender_name: str = Field(..., max_length=255, description="Full legal name of lender")
    policy_version: str = Field(..., max_length=20, description="Policy version number")
    status: str = Field(default="active", description="Policy status: active, draft, deprecated")
    effective_date: datetime = Field(..., description="Date when policy becomes effective")
    
    @field_validator('lender_id')
    def validate_lender_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('lender_id cannot be empty')
        return v


class LenderPolicyCreate(LenderPolicyBase):
    xml_content: str = Field(..., description="XML content of the policy file")
    
    @field_validator('xml_content')
    def validate_xml_content(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('xml_content cannot be empty')
        return v


class LenderPolicyUpdate(LenderPolicyBase):
    xml_content: Optional[str] = Field(None, description="Updated XML content of the policy file")
    
    @field_validator('xml_content')
    def validate_xml_content_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError('xml_content cannot be empty if provided')
        return v


class LenderPolicyResponse(LenderPolicyBase):
    id: int
    evaluations_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LenderPolicyMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    lender_id: str
    lender_name: str
    policy_version: str
    status: str
    effective_date: datetime
    created_at: datetime
    evaluations_count: int


class PolicyListResponse(BaseModel):
    policies: List[LenderPolicyMetadata]
    total: int
    limit: int
    offset: int


class PolicyEvaluationRequest(BaseModel):
    lender_id: str = Field(..., description="Lender identifier to evaluate against")
    applicant_data: dict = Field(..., description="Applicant information for evaluation")
    loan_amount: float = Field(..., gt=0, description="Requested loan amount")
    property_value: float = Field(..., gt=0, description="Property appraised value")
    
    @field_validator('lender_id')
    def validate_lender_id_eval(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('lender_id cannot be empty')
        return v


class PolicyEvaluationResponse(BaseModel):
    compliant: bool = Field(..., description="Whether application complies with policy")
    violations: List[str] = Field(default=[], description="List of policy violations if not compliant")
    qualifying_rate: Optional[float] = Field(None, description="Stress test rate used in evaluation")