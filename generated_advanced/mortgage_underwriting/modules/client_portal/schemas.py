from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

class UserRoleEnum(str, Enum):
    CLIENT = "client"
    BROKER = "broker"


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    role: Optional[UserRoleEnum] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class DashboardProgressResponse(BaseModel):
    current_status: str
    next_status: Optional[str] = None
    percent_complete: int = Field(..., ge=0, le=100)


class OutstandingDocumentItem(BaseModel):
    document_type: str
    required: bool
    uploaded: bool


class RecentMessageResponse(BaseModel):
    sender: str
    message: str
    timestamp: datetime


class KeyNumbersResponse(BaseModel):
    requested_mortgage: Decimal
    purchase_price: Decimal
    status: str


class ClientDashboardResponse(BaseModel):
    progress: DashboardProgressResponse
    outstanding_documents: List[OutstandingDocumentItem]
    recent_message: Optional[RecentMessageResponse] = None
    key_numbers: KeyNumbersResponse


class PipelineSummaryResponse(BaseModel):
    draft: int
    submitted: int
    in_review: int
    conditionally_approved: int
    approved: int
    closed: int


class FlaggedFileResponse(BaseModel):
    application_id: int
    reason: str
    days_overdue: Optional[int] = None


class RecentActivityResponse(BaseModel):
    activity_type: str
    description: str
    timestamp: datetime


class QuickActionResponse(BaseModel):
    action: str
    url: str


class BrokerDashboardResponse(BaseModel):
    pipeline_summary: PipelineSummaryResponse
    flagged_files: List[FlaggedFileResponse]
    recent_activity: List[RecentActivityResponse]
    quick_actions: List[QuickActionResponse]


class NotificationTypeEnum(str, Enum):
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_VERIFIED = "document_verified"
    DOCUMENT_REJECTED = "document_rejected"
    STATUS_CHANGED = "status_changed"
    MESSAGE_RECEIVED = "message_received"
    CONDITION_ADDED = "condition_added"


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    notification_type: NotificationTypeEnum
    title: str
    message: str
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[NotificationResponse]


class NotificationReadRequest(BaseModel):
    is_read: bool = True