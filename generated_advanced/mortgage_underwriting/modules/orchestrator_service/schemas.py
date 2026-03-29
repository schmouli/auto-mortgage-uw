from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class EmploymentType(str, Enum):
    SALARIED = "salaried"
    SELF_EMPLOYED = "self-employed"
    CONTRACT = "contract"


class AddressSchema(BaseModel):
    street: str = Field(..., max_length=255)
    city: str = Field(..., max_length=100)
    province: str = Field(..., max_length=2)
    postal_code: str = Field(..., max_length=10)


class BorrowerCreateSchema(BaseModel):
    full_name: str = Field(..., max_length=255)
    sin: str = Field(..., min_length=9, max_length=9, pattern=r"^\d{9}$")
    date_of_birth: datetime
    employment_type: EmploymentType
    gross_annual_income: Decimal = Field(..., gt=0)
    credit_score: int = Field(..., ge=300, le=900)
    address: AddressSchema


class DocumentUploadSchema(BaseModel):
    filename: str = Field(..., max_length=255)
    content_type: str = Field(..., max_length=100)
    s3_bucket: str = Field(..., max_length=255)
    s3_key: str = Field(..., max_length=1024)


class ApplicationCreateSchema(BaseModel):
    borrower: BorrowerCreateSchema
    lender_id: UUID
    property_value: Decimal = Field(..., gt=0)
    purchase_price: Decimal = Field(..., gt=0)
    mortgage_amount: Decimal = Field(..., gt=0)
    documents: List[DocumentUploadSchema] = Field(..., min_length=1)


class ApplicationStatus(str, Enum):
    SUBMITTED = "submitted"
    EXTRACTING = "extracting"
    EVALUATING = "evaluating"
    DECIDED = "decided"
    EXCEPTION = "exception"


class DecisionResultSchema(BaseModel):
    result: str = Field(..., max_length=20)
    confidence_score: Decimal
    gds_ratio: Decimal
    tds_ratio: Decimal
    ltv_ratio: Decimal
    cmhc_required: bool
    stress_test_rate: Decimal
    policy_flags: List[str]
    exceptions: List[dict]


class ApplicationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: ApplicationStatus
    borrower_id: UUID
    lender_id: UUID
    property_value: Decimal
    purchase_price: Decimal
    mortgage_amount: Decimal
    ltv_ratio: Optional[Decimal]
    insurance_required: bool
    insurance_premium: Optional[Decimal]
    decision_result: Optional[DecisionResultSchema]
    created_at: datetime
    updated_at: datetime
    created_by: str


class ApplicationListSchema(BaseModel):
    items: List[ApplicationSchema]
    total: int
    page: int
    size: int


class IdentityVerificationRequest(BaseModel):
    verified: bool
    notes: Optional[str] = None


class IdentityVerificationResponse(BaseModel):
    application_id: UUID
    verified: bool
    verified_at: datetime
    verified_by: str


class TransactionReportRequest(BaseModel):
    transaction_amount: Decimal = Field(..., gt=10000)
    transaction_type: str = Field(..., max_length=50)
    description: str = Field(..., max_length=500)


class RiskAssessmentResponse(BaseModel):
    client_id: UUID
    risk_level: str
    last_assessed: datetime
    findings: List[str]