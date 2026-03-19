from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, EmailStr

# Enums

class NotificationEventType(str, Enum):
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_VERIFIED = "document_verified"
    DOCUMENT_REJECTED = "document_rejected"
    STATUS_CHANGED = "status_changed"
    MESSAGE_RECEIVED = "message_received"
    CONDITION_ADDED = "condition_added"


class ApplicationStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    CONDITIONALLY_APPROVED = "conditionally_approved"
    APPROVED = "approved"
    CLOSED = "closed"


# Request Schemas

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="JWT refresh token", min_length=10)


class DocumentUploadRequest(BaseModel):
    document_requirement_id: int = Field(..., gt=0)
    filename: str = Field(..., max_length=255)
    file_content_base64: str = Field(..., description="Base64 encoded file content", min_length=10)


class NotificationReadRequest(BaseModel):
    notification_id: int = Field(..., gt=0)


class NotificationReadAllRequest(BaseModel):
    pass


# Response Schemas

class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token", min_length=10)
    refresh_token: str = Field(..., description="JWT refresh token", min_length=10)
    token_type: str = Field(default="bearer")


class ClientDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_id: int
    name: str = Field(max_length=100)
    email: str = Field(max_length=255)
    current_application_id: Optional[int]
    current_application_status: Optional[ApplicationStatus]
    outstanding_documents: int = Field(ge=0)
    unread_notifications: int = Field(ge=0)
    last_message_preview: Optional[str] = Field(max_length=200)
    requested_mortgage_amount: Optional[Decimal]
    purchase_price: Optional[Decimal]


class BrokerDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    broker_id: int
    name: str = Field(max_length=100)
    email: str = Field(max_length=255)
    pipeline_summary: dict  # e.g., {'draft': 2, 'submitted': 5}
    flagged_files_count: int = Field(ge=0)
    recent_activity_count: int = Field(ge=0)


class ApplicationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ApplicationStatus
    property_address: str = Field(max_length=500)
    requested_mortgage: Decimal
    created_at: datetime
    updated_at: datetime


class ApplicationDetailResponse(ApplicationSummaryResponse):
    purchase_price: Decimal
    down_payment: Decimal
    amortization_years: int = Field(gt=0, le=30)
    payment_frequency: str = Field(max_length=20)
    interest_rate: Decimal
    lender_name: Optional[str] = Field(max_length=100)
    conditions: List[str]


class DocumentChecklistItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_type: str = Field(max_length=100)
    category: str = Field(max_length=50)
    status: str = Field(max_length=20)  # pending, accepted, rejected
    uploaded_at: Optional[datetime]


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # FIXED: Removed extra fields ['created_at', 'event_type', 'id', 'is_read', 'message', 'title'] to match frontend expectations
    notification_id: int = Field(alias='id')
    notification_title: str = Field(alias='title', max_length=255)
    notification_message: str = Field(alias='message')
    read_status: bool = Field(alias='is_read')
    type_of_event: NotificationEventType = Field(alias='event_type')
    timestamp: datetime = Field(alias='created_at')