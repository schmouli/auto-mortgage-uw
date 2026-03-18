from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class MessageCreateRequest(BaseModel):
    recipient_id: int = Field(..., gt=0, description="Target user ID")
    body: str = Field(..., min_length=1, max_length=5000, description="Message content")


class MessageUpdateReadStatusRequest(BaseModel):
    is_read: bool = Field(True, description="Mark message as read")


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # FIXED: Align schema with DB model fields
    id: int
    application_id: int  # Added missing field
    sender_id: int       # Added missing field
    recipient_id: int    # Added missing field
    body: str
    is_read: bool
    sent_at: datetime
    read_at: Optional[datetime] = None


class ConditionCreateRequest(BaseModel):
    lender_submission_id: Optional[int] = Field(None, gt=0, description="Optional FK to lender submission")
    description: str = Field(..., min_length=1, max_length=2000, description="Condition description")
    condition_type: str = Field(..., pattern="^(document|information|other)$", description="Type of condition")
    required_by_date: Optional[datetime] = Field(None, description="Deadline for satisfaction")


class ConditionUpdateStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(satisfied|waived)$", description="New status")
    satisfied_by: Optional[int] = Field(None, gt=0, description="User who satisfied condition")


class ConditionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # FIXED: Align schema with DB model fields
    id: int
    application_id: int          # Added missing field
    lender_submission_id: Optional[int]  # Added missing field
    description: str
    condition_type: str
    status: str
    required_by_date: Optional[datetime]
    satisfied_at: Optional[datetime]
    satisfied_by: Optional[int]
    created_at: datetime


class PaginatedMessagesResponse(BaseModel):
    items: List[MessageResponse]
    total: int
    page: int
    page_size: int


class PaginatedConditionsResponse(BaseModel):
    items: List[ConditionResponse]
    total: int
    page: int
    page_size: int