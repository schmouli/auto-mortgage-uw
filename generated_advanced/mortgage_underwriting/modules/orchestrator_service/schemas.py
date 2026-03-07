from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Literal, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator

from mortgage_underwriting.modules.orchestrator.models import ApplicationStatus, EmploymentType

# --- Request Schemas ---

class BorrowerInfo(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    sin: str = Field(..., pattern=r'^\d{9}$', description="9-digit SIN")
    date_of_birth: str = Field(..., description="ISO 8601 date format YYYY-MM-DD")
    employment_type: EmploymentType
    gross_annual_income: Decimal = Field(..., gt=0)
    monthly_liability_payments: Optional[Decimal] = Field(default=Decimal('0.00'), ge=0)
    credit_score: Optional[int] = Field(None, ge=300, le=900)


class ApplicationCreateRequest(BaseModel):
    borrower_json: str = Field(..., description="JSON string of BorrowerInfo")
    property_value: Decimal = Field(..., gt=0)
    purchase_price: Decimal = Field(..., gt=0)
    mortgage_amount: Decimal = Field(..., gt=0)
    contract_interest_rate: Decimal = Field(..., gt=0)
    lender_id: str = Field(..., min_length=1)
    # documents handled separately in multipart form

    @field_validator('borrower_json')
    def validate_borrower_json(cls, v: str) -> str:
        try:
            import json
            data = json.loads(v)
            BorrowerInfo(**data)  # Validate structure
            return v
        except Exception as e:
            raise ValueError(f'Invalid borrower_json: {str(e)}')


class FINTRACIdentityVerifyRequest(BaseModel):
    verification_method: str = Field(..., min_length=1)
    verification_timestamp: datetime
    verifier_id: str = Field(..., min_length=1)


class FINTRACReportTransactionRequest(BaseModel):
    transaction_type: str = Field(..., min_length=1)
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="CAD", pattern=r'^[A-Z]{3}$')
    is_high_risk: bool = False
    report_data: Dict[str, Any] = {}


class ReprocessRequest(BaseModel):
    force: bool = False
    reason: Optional[str] = Field(None, max_length=500)


# --- Response Schemas ---

class ApplicationSubmitResponse(BaseModel):
    application_id: UUID
    borrower_id: UUID
    status: ApplicationStatus
    created_at: datetime
    pipeline_task_id: str  # Celery task ID

    model_config = ConfigDict(from_attributes=True)


class ApplicationStatusResponse(BaseModel):
    id: UUID
    borrower_id: UUID
    lender_id: str
    status: ApplicationStatus
    property_value: Decimal
    purchase_price: Decimal
    mortgage_amount: Decimal
    contract_interest_rate: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    id: UUID
    document_type: str
    s3_key: str
    file_size: int
    mime_type: str
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FINTRACVerificationStatusResponse(BaseModel):
    id: UUID
    application_id: UUID
    client_id: UUID
    transaction_type: str
    amount: Decimal
    currency: str
    is_high_risk: bool
    verification_status: str
    report_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RiskAssessmentResponse(BaseModel):
    client_id: UUID
    risk_level: Literal["low", "medium", "high"]
    last_assessment_date: datetime
    factors: List[str]
    overall_score: int = Field(..., ge=0, le=100)


class ApplicationListResponse(BaseModel):
    items: List[ApplicationStatusResponse]
    total: int
    page: int
    size: int

    model_config = ConfigDict(from_attributes=True)