from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

# --- Document Schemas ---

class DocumentBase(BaseModel):
    document_type: str = Field(..., max_length=50)
    file_name: str = Field(..., max_length=255)
    file_size: int = Field(..., ge=0)
    mime_type: str = Field(..., max_length=100)
    status: str = Field(default='pending', pattern='^(pending|accepted|rejected)$')


class DocumentCreate(DocumentBase):
    application_id: int = Field(..., gt=0)
    notes: Optional[str] = Field(None, max_length=500)


class DocumentUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern='^(pending|accepted|rejected)$')
    rejection_reason: Optional[str] = Field(None, max_length=1000)
    is_verified: Optional[bool] = None
    verified_by: Optional[int] = None


class DocumentResponse(DocumentBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: int
    uploaded_by: int
    # FIXED: Removed file_path from response to prevent exposure of internal paths
    rejection_reason: Optional[str]
    is_verified: bool
    verified_by: Optional[int]
    verified_at: Optional[datetime]
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime


class DocumentPublic(DocumentBase):  # For safe API exposure
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    rejection_reason: Optional[str]
    is_verified: bool
    verified_at: Optional[datetime]
    uploaded_at: datetime


class DocumentVerificationUpdate(BaseModel):
    is_verified: bool = Field(..., description="Set to true to mark as verified")
    verified_by: int = Field(..., gt=0, description="User ID of verifier")


class DocumentRejectionUpdate(BaseModel):
    rejection_reason: str = Field(..., max_length=1000, description="Reason for rejecting the document")


# --- Document Requirement Schemas ---

class DocumentRequirementBase(BaseModel):
    document_type: str = Field(..., max_length=50)
    is_required: bool = True
    is_received: bool = False
    due_date: Optional[datetime] = None


class DocumentRequirementCreate(DocumentRequirementBase):
    application_id: int = Field(..., gt=0)


class DocumentRequirementUpdate(BaseModel):
    is_received: Optional[bool] = None
    due_date: Optional[datetime] = None


class DocumentRequirementResponse(DocumentRequirementBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: int
    created_at: datetime
    updated_at: datetime


# --- Checklist Response ---

class ReceivedDocumentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    document_id: int
    file_name: str
    status: str
    is_verified: bool
    uploaded_at: datetime


class ChecklistItem(BaseModel):
    document_type: str
    is_required: bool
    is_received: bool
    due_date: Optional[datetime]
    received_documents: List[ReceivedDocumentItem] = []


class DocumentChecklistResponse(BaseModel):
    application_id: int
    checklist_items: List[ChecklistItem]