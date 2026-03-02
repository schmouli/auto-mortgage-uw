```python
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class VerificationMethod(str, Enum):
    IN_PERSON = "in_person"
    CREDIT_FILE = "credit_file"
    DUAL_PROCESS = "dual_process"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReportType(str, Enum):
    LARGE_CASH_TRANSACTION = "large_cash_transaction"
    SUSPICIOUS_TRANSACTION = "suspicious_transaction"
    TERRORIST_PROPERTY = "terrorist_property"


# Request Schemas
class IdentityVerificationCreateRequest(BaseModel):
    verification_method: VerificationMethod = Field(..., description="Method used for verification")
    id_type: str = Field(..., max_length=100, description="Type of ID presented (e.g., passport)")
    id_number_encrypted: str = Field(..., description="Encrypted ID number")
    id_expiry_date: datetime = Field(..., description="Expiry date of the ID document")
    id_issuing_province: Optional[str] = Field(None, max_length=100, description="Province/state that issued the ID")
    verified_by: int = Field(..., gt=0, description="ID of the user who performed verification")
    is_pep: bool = Field(default=False, description="Is Politically Exposed Person")
    is_hio: bool = Field(default=False, description="Is High Impact Organization")


class TransactionReportCreateRequest(BaseModel):
    report_type: ReportType = Field(..., description="Type of FINTRAC report being filed")
    amount: Decimal = Field(..., gt=0, description="Transaction amount")
    currency: str = Field("CAD", max_length=3, description="Currency code (ISO 4217)")
    report_date: datetime = Field(..., description="Date of the transaction")
    created_by: int = Field(..., gt=0, description="ID of the user creating the report")

    @validator('currency')
    def validate_currency(cls, v):
        if len(v) != 3 or not v.isalpha():
            raise ValueError('Invalid currency code')
        return v.upper()


# Response Schemas
class IdentityVerificationResponse(BaseModel):
    id: int
    application_id: int
    client_id: int
    verification_method: VerificationMethod
    id_type: str
    id_expiry_date: datetime
    id_issuing_province: Optional[str]
    verified_by: int
    verified_at: datetime
    is_pep: bool
    is_hio: bool
    risk_level: RiskLevel
    record_created_at: datetime


class TransactionReportResponse(BaseModel):
    id: int
    application_id: int
    report_type: ReportType
    amount: Decimal
    currency: str
    report_date: datetime
    submitted_to_fintrac_at: Optional[datetime]
    fintrac_reference_number: Optional[str]
    created_by: int
    created_at: datetime


class RiskAssessmentResponse(BaseModel):
    client_id: int
    requires_enhanced_due_diligence: bool
    risk_level: RiskLevel
    is_pep: bool
    is_hio: bool
    last_verification_date: Optional[datetime]


class VerificationStatusResponse(BaseModel):
    has_verification: bool
    latest_verification: Optional[IdentityVerificationResponse]
    requires_enhanced_due_diligence: bool


class ReportsListResponse(BaseModel):
    reports: List[TransactionReportResponse]
    total_count: int
```