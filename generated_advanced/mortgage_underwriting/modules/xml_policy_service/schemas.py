from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class LtvLimits(BaseModel):
    insured: Decimal = Field(..., gt=0, le=95)
    conventional: Decimal = Field(..., gt=0, le=80)


class AmortizationLimits(BaseModel):
    insured: int = Field(..., ge=1, le=30)
    conventional: int = Field(..., ge=1, le=35)


class PropertyTypes(BaseModel):
    allowed: list[str] = Field(..., min_length=1)
    excluded: list[str] = Field(default=[])


class PolicyRules(BaseModel):
    ltv_max: LtvLimits
    gds_max: Decimal = Field(..., ge=0, le=100)
    tds_max: Decimal = Field(..., ge=0, le=100)
    credit_score_min: int = Field(..., ge=300, le=900)
    amortization_max: AmortizationLimits
    property_types: PropertyTypes


class LenderPolicySummary(BaseModel):
    lender_id: str = Field(..., pattern=r'^[A-Z]{3,6}$')
    lender_name: str = Field(..., max_length=100)
    version: str = Field(..., pattern=r'^\d+\.\d+\.\d+$')
    is_active: bool
    effective_date: datetime
    xml_hash: str


class LenderPolicyDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    lender_id: str
    lender_name: str
    version: str
    is_active: bool
    effective_date: datetime
    policy_rules: PolicyRules
    xml_hash: str
    created_by: str
    created_at: datetime


class LenderPolicyCreate(BaseModel):
    lender_id: str = Field(..., pattern=r'^[A-Z]{3,6}$')
    lender_name: str = Field(..., max_length=100)
    version: str = Field(..., pattern=r'^\d+\.\d+\.\d+$')
    is_active: bool = True
    effective_date: datetime
    policy_xml: str = Field(..., min_length=100)


class LenderPolicyUpdate(BaseModel):
    is_active: Optional[bool] = None
    effective_date: Optional[datetime] = None
    policy_xml: Optional[str] = Field(None, min_length=100)