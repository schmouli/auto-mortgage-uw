from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

# Request Schemas

class FintracVerificationRequest(BaseModel):
    client_id: int = Field(..., gt=0)
    verification_method: str = Field(..., pattern="^(in_person|credit_file|dual_process)$")
    id_type: str = Field(..., min_length=1, max_length=50)
    id_number: str = Field(..., min_length=1, max_length=100)
    id_expiry_date: date = Field(...)
    id_issuing_province: str = Field(..., min_length=2, max_length=2)
    is_pep: bool = False
    is_hio: bool = False

    @field_validator('id_expiry_date')
    @classmethod
    def validate_id_not_expired(cls, v: date) -> date:
        from datetime import date as dt_date
        if v < dt_date.today():
            raise ValueError('ID expiry date cannot be in the past')
        return v


class FintracTransactionReportRequest(BaseModel):
    report_type: str = Field(..., pattern="^(large_cash_transaction|suspicious_transaction|terrorist_property)$")
    amount: Decimal = Field(..., gt=0)
    currency: str = Field("CAD", pattern="^[A-Z]{3}$")
    created_by: int = Field(..., gt=0)

# Response Schemas

class FintracVerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    verification_method: str
    risk_level: str
    verified_at: datetime


class FintracVerificationStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: int
    client_id: int
    verification_method: str
    id_type: str
    id_expiry_date: date
    id_issuing_province: str
    verified_at: datetime
    is_pep: bool
    is_hio: bool
    risk_level: str
    record_created_at: datetime


class FintracReportListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    report_type: str
    amount: Decimal
    currency: str
    report_date: datetime
    fintrac_reference_number: Optional[str] = None


class FintracRiskAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    client_id: int
    risk_level: str
    is_pep: bool
    is_hio: bool
    requires_enhanced_due_diligence: bool
    last_verified_at: datetime