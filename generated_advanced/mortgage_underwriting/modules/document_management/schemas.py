from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

class DocumentTypeEnum(str, Enum):
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

class DocumentStatusEnum(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class DocumentUploadRequest(BaseModel):
    document_type: DocumentTypeEnum = Field(...)

class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    doc_id: int
    file_name: str
    status: DocumentStatusEnum
    message: str

class DocumentVerifyRequest(BaseModel):
    verified_by: int = Field(..., gt=0)

class DocumentRejectRequest(BaseModel):
    rejection_reason: str = Field(..., max_length=1000)

class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    doc_id: int
    file_name: str
    status: DocumentStatusEnum
    is_verified: bool
    uploaded_at: datetime

class DocumentRequirementItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_type: DocumentTypeEnum
    is_required: bool
    is_received: bool
    due_date: Optional[datetime]
    days_until_due: Optional[int]
    uploaded_documents: List[DocumentSummary]

class DocumentChecklistResponse(BaseModel):
    application_id: int
    requirements: List[DocumentRequirementItem]
    overall_status: str  # complete, incomplete, overdue

class DocumentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_type: DocumentTypeEnum
    file_name: str
    status: DocumentStatusEnum
    is_verified: bool
    uploaded_at: datetime

class DocumentDownloadResponse(BaseModel):
    download_url: str
    expires_at: datetime