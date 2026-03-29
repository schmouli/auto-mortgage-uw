from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class DocumentType(str):
    IDENTITY_GOVERNMENT_ID = "government_id"
    IDENTITY_PROOF_OF_SIN = "proof_of_sin"
    INCOME_T4_SLIP = "t4_slip"
    INCOME_NOA = "noa"
    INCOME_PAY_STUB = "pay_stub"
    INCOME_EMPLOYMENT_LETTER = "employment_letter"
    INCOME_T1_GENERAL = "t1_general"
    INCOME_FINANCIAL_STATEMENTS = "financial_statements"
    INCOME_RENTAL_INCOME_STATEMENT = "rental_income_statement"
    PROPERTY_PURCHASE_AGREEMENT = "purchase_agreement"
    PROPERTY_MLS_LISTING = "mls_listing"
    PROPERTY_PROPERTY_TAX_BILL = "property_tax_bill"
    PROPERTY_CONDO_STATUS_CERT = "condo_status_cert"
    BANKING_BANK_STATEMENT = "bank_statement"
    BANKING_VOID_CHEQUE = "void_cheque"
    DOWN_PAYMENT_GIFT_LETTER = "gift_letter"
    DOWN_PAYMENT_RRSP_WITHDRAWAL = "rrsp_withdrawal_confirmation"
    DOWN_PAYMENT_SALE_PROCEEDS = "sale_proceeds_confirmation"
    OTHER_EXISTING_MORTGAGE = "existing_mortgage_statement"
    OTHER_DIVORCE_DEGREE = "divorce_decree"
    OTHER_BANKRUPTCY_DISCHARGE = "bankruptcy_discharge"


class DocumentBase(BaseModel):
    document_type: str = Field(..., description="Type of document being uploaded")
    file_name: str = Field(..., max_length=255, description="Original filename")
    file_size: int = Field(..., gt=0, le=10485760, description="File size in bytes (max 10MB)")
    mime_type: str = Field(..., description="MIME type of the file")


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(accepted|rejected)$")
    rejection_reason: Optional[str] = Field(None, max_length=1000)
    is_verified: Optional[bool] = None
    verified_by: Optional[int] = None


class DocumentResponse(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    uploaded_by: Optional[int]
    status: str
    rejection_reason: Optional[str]
    is_verified: bool
    verified_by: Optional[int]
    verified_at: Optional[datetime]
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime


class DocumentRequirementBase(BaseModel):
    document_type: str = Field(..., description="Required document type")
    is_required: bool = True
    is_received: bool = False
    due_date: Optional[datetime] = None


class DocumentRequirementCreate(DocumentRequirementBase):
    pass


class DocumentRequirementUpdate(DocumentRequirementBase):
    is_received: Optional[bool] = None
    due_date: Optional[datetime] = None


class DocumentRequirementResponse(DocumentRequirementBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    created_at: datetime
    updated_at: datetime


class DocumentChecklistItem(BaseModel):
    document_type: str
    is_required: bool
    is_received: bool
    due_date: Optional[datetime] = None


class DocumentChecklistResponse(BaseModel):
    items: List[DocumentChecklistItem]
    total_required: int
    total_received: int