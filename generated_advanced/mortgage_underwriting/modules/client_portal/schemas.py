from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

# --- AUTH SCHEMAS ---


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    client_id: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# --- DASHBOARD SCHEMAS ---


class ApplicationStatusProgress(BaseModel):
    status: str
    label: str
    completed_at: Optional[datetime] = None


class OutstandingDocumentItem(BaseModel):
    id: int
    document_type: str
    is_uploaded: bool
    is_verified: bool
    rejection_reason: Optional[str] = None


class DashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: int
    current_status: str
    progress_steps: List[ApplicationStatusProgress]
    outstanding_documents: List[OutstandingDocumentItem]
    latest_message: Optional[str] = None
    requested_mortgage: Decimal
    purchase_price: Decimal


# --- APPLICATION SCHEMAS ---


class ApplicationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    purchase_price: Decimal


class CreateApplicationRequest(BaseModel):
    purchase_price: Decimal = Field(..., gt=0)
    down_payment: Decimal = Field(..., gt=0)


class UpdateApplicationRequest(BaseModel):
    status: Optional[str] = None


class ApplicationDetail(ApplicationSummary):
    client_id: int
    property_address: Optional[str] = None
    lender_name: Optional[str] = None


# --- DOCUMENT SCHEMAS ---


class DocumentUploadRequest(BaseModel):
    document_type: str
    file_name: str = Field(..., max_length=255)
    file_size: int = Field(..., gt=0, le=10485760)  # Max 10MB
    mime_type: str


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_type: str
    status: str
    uploaded_at: datetime


class DocumentChecklistItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_type: str
    is_required: bool
    is_uploaded: bool
    is_verified: bool
    rejection_reason: Optional[str] = None


class DocumentChecklistResponse(BaseModel):
    items: List[DocumentChecklistItem]


# --- NOTIFICATION SCHEMAS ---


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message: str
    notification_type: str
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]
    unread_count: int


class MarkNotificationReadRequest(BaseModel):
    is_read: bool = True


class MarkAllNotificationsReadRequest(BaseModel):
    is_read: bool = True