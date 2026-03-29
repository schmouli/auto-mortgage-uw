from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class LenderPolicyBase(BaseModel):
    lender_id: str = Field(..., max_length=50, description="Unique identifier for the lender")
    name: str = Field(..., max_length=255, description="Lender name")
    version: str = Field(..., max_length=20, description="Policy version")


class LenderPolicyCreate(LenderPolicyBase):
    xml_content: str = Field(..., description="XML policy content")


class LenderPolicyUpdate(BaseModel):
    xml_content: str = Field(..., description="Updated XML policy content")


class LenderPolicyResponse(LenderPolicyBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PolicyEvaluationRequest(BaseModel):
    policy_id: int = Field(..., gt=0, description="ID of the policy to evaluate against")
    application_data: dict = Field(..., description="Application data to evaluate")


class PolicyEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    # FIXED: Removed extra fields that don't match the model schema
    # Only including fields that should be returned to the client
    result: bool
    details: Optional[str] = None


class PolicyListResponse(BaseModel):
    items: list[LenderPolicyResponse]
    total: int
    page: int
    size: int