from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class FintracVerificationBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    client_id: UUID = Field(..., description="FK to clients table")
    verification_method: Literal["in_person", "credit_file", "dual_process"] = Field(..., description="Method used for identity verification")
    id_type: Literal["passport", "drivers_license", "provincial_id", "certificate_of_citizenship"] = Field(..., description="Type of ID presented")
    id_number: str = Field(..., min_length=1, max_length=100, description="Plaintext ID number (will be encrypted before storage)")
    id_expiry_date: datetime = Field(..., description="Expiry date of the ID document")
    id_issuing_province: str = Field(..., min_length=2, max_length=2, description="Province code where ID was issued")
    is_pep: bool = Field(default=False, description="Politically Exposed Person flag")
    is_hio: bool = Field(default=False, description="High Integrity Origin flag")
    risk_level: Literal["low", "medium", "high"] = Field(default="low", description="Client risk level assessment")
    source_of_funds: Optional[str] = Field(None, max_length=500, description="Source of funds explanation (for EDD)")
    occupation: Optional[str] = Field(None, max_length=100, description="Client's occupation (for EDD)")
    employer: Optional[str] = Field(None, max_length=100, description="Client's employer (for EDD)")


class FintracVerificationCreate(FintracVerificationBase):
    pass


class FintracVerificationResponse(FintracVerificationBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: UUID
    verified_by: UUID
    verified_at: datetime
    requires_enhanced_due_diligence: bool = Field(..., description="Computed: true if high risk, PEP, or HIO")
    created_at: datetime


class FintracReportBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    report_type: Literal["large_cash_transaction", "suspicious_transaction", "terrorist_property"] = Field(..., description="Type of FINTRAC report being filed")
    amount: Decimal = Field(..., gt=0, description="Transaction amount in specified currency")
    currency: Literal["CAD", "USD", "EUR", "GBP"] = Field(default="CAD", description="Currency of transaction amount")
    report_date: datetime = Field(..., description="Date of the reported transaction")


class FintracReportCreate(FintracReportBase):
    pass


class FintracReportResponse(FintracReportBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: UUID
    submitted_to_fintrac_at: Optional[datetime] = None
    fintrac_reference_number: Optional[str] = None
    created_by: UUID
    created_at: datetime


class RiskAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    client_id: UUID
    risk_level: Literal["low", "medium", "high"]
    is_pep: bool
    is_hio: bool
    last_verification_date: Optional[datetime] = None
    requires_enhanced_due_diligence: bool