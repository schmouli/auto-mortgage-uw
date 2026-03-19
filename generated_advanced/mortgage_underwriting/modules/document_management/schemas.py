from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

# Enums matching the models


class DocumentStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class DocumentCategory(str, Enum):
    IDENTITY = "IDENTITY"
    INCOME = "INCOME"
    PROPERTY = "PROPERTY"
    BANKING = "BANKING"
    DOWN_PAYMENT = "DOWN_PAYMENT"
    OTHER = "OTHER"


class DocumentType(str, Enum):
    GOVERNMENT_ID = "government_id"
    PROOF_OF_SIN = "proof_of_sin"
    T4_SLIP = "t4_slip"
    NOA = "noa"
    PAY_STUB = "pay_stub"
    EMPLOYMENT_LETTER = "employment_letter"
    T1_GENERAL = "t1_general"
    FINANCIAL_STATEMENTS = "financial_statements"
    RENTAL_INCOME_STATEMENT = "rental_income_statement"
    PURCHASE_AGREEMENT = "purchase_agreement"
    MLS_LISTING = "mls_listing"
    PROPERTY_TAX_BILL = "property_tax_bill"
    CONDO_STATUS_CERT = "condo_status_cert"
    BANK_STATEMENT = "bank_statement"
    VOID_CHEQUE = "void_cheque"
    GIFT_LETTER = "gift_letter"
    RRSP_WITHDRAWAL_CONFIRMATION = "rrsp_withdrawal_confirmation"
    SALE_PROCEEDS_CONFIRMATION = "sale_proceeds_confirmation"
    EXISTING_MORTGAGE_STATEMENT = "existing_mortgage_statement"
    DIVORCE_DECREE = "divorce_decree"
    BANKRUPTCY_DISCHARGE = "bankruptcy_discharge"


# Request/Response Schemas


class DocumentRequirementBase(BaseModel):
    document_type: DocumentType
    category: DocumentCategory
    is_required: bool = True
    is_received: bool = False
    due_date: Optional[datetime] = None


class DocumentRequirementCreate(DocumentRequirementBase):
    pass


class DocumentRequirementUpdate(BaseModel):
    is_received: Optional[bool] = None
    due_date: Optional[datetime] = None


class DocumentRequirementResponse(DocumentRequirementBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    created_at: datetime
    updated_at: datetime


class DocumentBase(BaseModel):
    document_type: DocumentType
    file_name: str = Field(..., max_length=255)
    file_size: int = Field(..., gt=0)
    mime_type: str = Field(..., max_length=100)


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    status: Optional[DocumentStatus] = None
    rejection_reason: Optional[str] = Field(None, max_length=1000)
    is_verified: Optional[bool] = None
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None


class DocumentResponse(DocumentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    uploaded_by: Optional[int]
    status: DocumentStatus
    rejection_reason: Optional[str]
    is_verified: bool
    verified_by: Optional[int]
    verified_at: Optional[datetime]
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime


class ChecklistItem(BaseModel):
    document_type: DocumentType
    category: DocumentCategory
    is_required: bool
    is_received: bool
    due_date: Optional[datetime]
    days_until_due: Optional[int]
    received_document_id: Optional[int]
    received_at: Optional[datetime]
    status: DocumentStatus


class ChecklistResponse(BaseModel):
    application_id: int
    overall_status: str = Field(..., pattern="^(pending|complete|overdue)$")
    requirements: List[ChecklistItem]
    missing_required_count: int
    pending_verification_count: int


class VerificationRequest(BaseModel):
    verified_by: int
    verified_at: datetime


class RejectionRequest(BaseModel):
    rejection_reason: str = Field(..., max_length=1000)


class UploadDocumentRequest(BaseModel):
    document_type: DocumentType
    file_name: str = Field(..., max_length=255)
    file_size: int = Field(..., gt=0, le=10485760)  # Max 10MB
    mime_type: str = Field(..., max_length=100, pattern="^(application/pdf|image/jpeg|image/png|image/heic)$")