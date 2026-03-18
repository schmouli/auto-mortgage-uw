from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

# Enums matching models


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


class DocumentStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class DocumentRequirementCategory(str, Enum):
    IDENTITY = "IDENTITY"
    INCOME = "INCOME"
    PROPERTY = "PROPERTY"
    BANKING = "BANKING"
    DOWN_PAYMENT = "DOWN_PAYMENT"
    OTHER = "OTHER"

# Request/Response Schemas


class DocumentUploadRequest(BaseModel):
    document_type: DocumentType = Field(..., description="Type of document being uploaded")
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes about the document")


class DocumentCreate(BaseModel):
    application_id: int = Field(..., gt=0)
    uploaded_by: int = Field(..., gt=0)
    document_type: DocumentType
    file_name: str = Field(..., max_length=255)
    file_path: str = Field(..., max_length=500)
    file_size: int = Field(..., ge=0)
    mime_type: str = Field(..., max_length=100)
    status: DocumentStatus = Field(default=DocumentStatus.PENDING)


class DocumentUpdate(BaseModel):
    status: Optional[DocumentStatus] = None
    rejection_reason: Optional[str] = Field(None, max_length=1000)
    is_verified: Optional[bool] = None
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: int
    document_type: DocumentType
    file_name: str
    file_size: int
    mime_type: str
    status: DocumentStatus
    rejection_reason: Optional[str] = None
    is_verified: bool
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime


class DocumentRequirementCreate(BaseModel):
    application_id: int = Field(..., gt=0)
    document_type: DocumentType
    category: DocumentRequirementCategory
    is_required: bool = True
    is_received: bool = False
    due_date: Optional[datetime] = None


class DocumentRequirementUpdate(BaseModel):
    is_received: Optional[bool] = None
    due_date: Optional[datetime] = None


class DocumentRequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: int
    document_type: DocumentType
    category: DocumentRequirementCategory
    is_required: bool
    is_received: bool
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ReceivedDocumentInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    file_name: str
    status: DocumentStatus
    is_verified: bool
    uploaded_at: datetime


class ChecklistItem(BaseModel):
    document_type: DocumentType
    category: DocumentRequirementCategory
    is_required: bool
    is_received: bool
    due_date: Optional[datetime] = None
    status: str  # satisfied, pending, overdue
    received_documents: List[ReceivedDocumentInfo]


class DocumentChecklistResponse(BaseModel):
    application_id: int
    checklist_items: List[ChecklistItem]
    overall_status: str  # complete, incomplete
    missing_required_count: int


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    page: int
    size: int