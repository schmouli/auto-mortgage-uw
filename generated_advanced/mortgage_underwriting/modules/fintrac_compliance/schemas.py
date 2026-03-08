from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class VerifyIdentityRequest(BaseModel):
    client_id: int = Field(..., gt=0, description="Client ID associated with the application")
    verification_method: str = Field(..., pattern="^(in_person|credit_file|dual_process)$", description="Method used for verification")
    id_type: str = Field(..., pattern="^(drivers_license|passport|provincial_id|other)$", description="Type of identification document")
    id_number: str = Field(..., min_length=1, description="Plaintext ID number to be encrypted at rest")
    id_expiry_date: date = Field(..., description="Expiry date of the ID document")
    id_issuing_province: Optional[str] = Field(None, max_length=2, description="Province code where ID was issued")
    is_pep: bool = Field(False, description="Politically Exposed Person flag")
    is_hio: bool = Field(False, description="Head of International Organization flag")
    risk_level: str = Field("low", pattern="^(low|medium|high)$", description="Risk level assessment")


class VerifyIdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    verification_id: int = Field(..., description="ID of the verification record")
    application_id: int = Field(..., description="Application ID")
    client_id: int = Field(..., description="Client ID")
    verification_method: str = Field(..., description="Verification method used")
    id_type: str = Field(..., description="Type of identification document")
    id_number: str = Field(..., description="Masked ID number")
    id_expiry_date: date = Field(..., description="Expiry date of the ID document")
    id_issuing_province: Optional[str] = Field(None, description="Province code where ID was issued")
    verified_by: int = Field(..., description="User ID who performed verification")
    verified_at: datetime = Field(..., description="Timestamp when verification was completed")
    is_pep: bool = Field(..., description="Politically Exposed Person flag")
    is_hio: bool = Field(..., description="Head of International Organization flag")
    risk_level: str = Field(..., description="Risk level assessment")
    enhanced_due_diligence_required: bool = Field(..., description="Whether enhanced due diligence is required")
    created_at: datetime = Field(..., description="Record creation timestamp")


class ReportTransactionRequest(BaseModel):
    report_type: str = Field(..., pattern="^(large_cash_transaction|suspicious_transaction|terrorist_property)$", description="Type of transaction report")
    amount: Decimal = Field(..., gt=0, description="Transaction amount in CAD")
    currency: str = Field("CAD", max_length=3, description="Currency code")
    report_date: datetime = Field(..., description="Date/time of the transaction")


class ReportTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    report_id: int = Field(..., description="ID of the report")
    application_id: int = Field(..., description="Application ID")
    report_type: str = Field(..., description="Type of transaction report")
    amount: Decimal = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Currency code")
    report_date: datetime = Field(..., description="Date/time of the transaction")
    submitted_to_fintrac_at: Optional[datetime] = Field(None, description="When report was submitted to FINTRAC")
    fintrac_reference_number: Optional[str] = Field(None, description="Reference number from FINTRAC")
    created_by: int = Field(..., description="User ID who created the report")
    created_at: datetime = Field(..., description="Record creation timestamp")


class RiskAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    client_id: int = Field(..., description="Client ID")
    risk_level: str = Field(..., description="Current risk level")
    is_pep: bool = Field(..., description="Politically Exposed Person flag")
    is_hio: bool = Field(..., description="Head of International Organization flag")
    enhanced_due_diligence_required: bool = Field(..., description="Whether enhanced due diligence is required")
    last_verification_date: Optional[datetime] = Field(None, description="Most recent verification timestamp")