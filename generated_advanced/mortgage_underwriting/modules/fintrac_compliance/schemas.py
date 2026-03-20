from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

# --- Identity Verification Schemas ---


class IdentityVerificationBase(BaseModel):
    client_id: int = Field(..., gt=0, description="FK to clients table")
    verification_method: str = Field(..., pattern="^(in_person|credit_file|dual_process)$")
    id_type: str = Field(..., max_length=50)
    id_number: str = Field(..., description="Plaintext ID number - will be encrypted at rest")
    id_expiry_date: datetime
    id_issuing_province: str = Field(..., min_length=2, max_length=2)
    is_pep: bool = False
    is_hio: bool = False

    @field_validator('id_expiry_date')
    @classmethod
    def validate_id_expiry_not_past(cls, v: datetime) -> datetime:
        if v.date() < datetime.today().date():
            raise ValueError('ID expiry date cannot be in the past')
        return v


class IdentityVerificationCreate(IdentityVerificationBase):
    pass


class IdentityVerificationUpdate(BaseModel):
    verification_method: Optional[str] = Field(None, pattern="^(in_person|credit_file|dual_process)$")
    id_type: Optional[str] = Field(None, max_length=50)
    id_number: Optional[str] = Field(None, description="Plaintext ID number - will be encrypted at rest")
    id_expiry_date: Optional[datetime] = None
    id_issuing_province: Optional[str] = Field(None, min_length=2, max_length=2)
    is_pep: Optional[bool] = None
    is_hio: Optional[bool] = None

    @field_validator('id_expiry_date')
    @classmethod
    def validate_id_expiry_not_past(cls, v: datetime) -> datetime:
        if v and v.date() < datetime.today().date():
            raise ValueError('ID expiry date cannot be in the past')
        return v


class IdentityVerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    verification_id: int = Field(..., alias="id")
    application_id: int
    client_id: int
    verification_method: str
    id_type: str
    id_expiry_date: datetime
    id_issuing_province: str
    verified_by: Optional[int]
    verified_at: datetime
    is_pep: bool
    is_hio: bool
    risk_level: str
    record_created_at: datetime


# --- Transaction Report Schemas ---


class TransactionReportBase(BaseModel):
    report_type: str = Field(..., pattern="^(large_cash_transaction|suspicious_transaction|terrorist_property)$")
    amount: Decimal = Field(..., gt=0)
    currency: str = Field("CAD", pattern="^[A-Z]{3}$")
    report_date: datetime


class TransactionReportCreate(TransactionReportBase):
    pass


class TransactionReportUpdate(BaseModel):
    report_type: Optional[str] = Field(None, pattern="^(large_cash_transaction|suspicious_transaction|terrorist_property)$")
    amount: Optional[Decimal] = Field(None, gt=0)
    currency: Optional[str] = Field(None, pattern="^[A-Z]{3}$")
    report_date: Optional[datetime] = None


class TransactionReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: int
    report_type: str
    amount: Decimal
    currency: str
    report_date: datetime
    submitted_to_fintrac_at: Optional[datetime]
    fintrac_reference_number: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime


# --- Risk Assessment Schemas ---


class RiskAssessmentResponse(BaseModel):
    client_id: int
    risk_level: str
    risk_score: int
    requires_enhanced_due_diligence: bool
    last_verification_date: Optional[datetime]