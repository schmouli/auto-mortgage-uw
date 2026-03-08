from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


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
    DIVORCE_DEGREE = "divorce_decree"
    BANKRUPTCY_DISCHARGE = "bankruptcy_discharge"


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


class DocumentUploadRequest(BaseModel):
    document_type: DocumentType = Field(..., description="Type of document being uploaded")
    description: Optional[str] = Field(None, max_length=255, description="Optional description of the document")


class DocumentCreate(BaseModel):
    application_id: int = Field(..., gt=0)
    uploaded_by: Optional[int] = Field(None, gt=0)
    document_type: str = Field(..., max_length=50)
    file_name: str = Field(..., max_length=255)
    file_path: str = Field(...)
    file_size: int = Field(..., ge=0)
    mime_type: str = Field(..., max_length=100)
    status: str = Field(default="pending", max_length=20)


class DocumentUpdate(BaseModel):
    status: Optional[str] = Field(None, max_length=20)
    rejection_reason: Optional[str] = Field(None)
    is_verified: Optional[bool] = Field(None)
    verified_by: Optional[int] = Field(None, gt=0)
    verified_at: Optional[datetime] = Field(None)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: int
    document_type: str
    file_name: str
    status: str
    is_verified: bool
    uploaded_at: datetime


class DocumentRequirementCreate(BaseModel):
    application_id: int = Field(..., gt=0)
    document_type: str = Field(..., max_length=50)
    is_required: bool = Field(default=True)
    is_received: bool = Field(default=False)
    due_date: Optional[datetime] = Field(None)


class DocumentRequirementUpdate(BaseModel):
    is_received: Optional[bool] = Field(None)
    due_date: Optional[datetime] = Field(None)


class ChecklistItemResponse(BaseModel):
    document_type: str
    category: DocumentCategory
    is_required: bool
    is_received: bool
    due_date: Optional[datetime]
    status: str  # overdue|pending|received
    received_at: Optional[datetime]
    document_id: Optional[int]


class ChecklistResponse(BaseModel):
    application_id: int
    checklist: List[ChecklistItemResponse]
    overall_completion: dict  # {"required_received": int, "required_total": int, "percentage": float}