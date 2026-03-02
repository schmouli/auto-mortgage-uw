```python
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from enum import StrEnum


class ConditionType(StrEnum):
    DOCUMENT = "document"
    INFORMATION = "information"
    OTHER = "other"


class ConditionStatus(StrEnum):
    OUTSTANDING = "outstanding"
    SATISFIED = "satisfied"
    WAIVED = "waived"


# Message Schemas
class MessageCreateRequest(BaseModel):
    recipient_id: int = Field(..., gt=0, description="Recipient user ID")
    body: str = Field(..., min_length=1, max_length=5000, description="Message content")


class MessageUpdateReadRequest(BaseModel):
    is_read: bool = Field(True, description="Mark message as read")


class MessageResponse(BaseModel):
    id: int
    application_id: int
    sender_id: int
    recipient_id: int
    body: str
    is_read: bool
    sent_at: datetime
    read_at: Optional[datetime]

    class Config:
        from_attributes = True


# Condition Schemas
class ConditionCreateRequest(BaseModel):
    lender_submission_id: Optional[int] = Field(None, gt=0, description="Lender submission ID")
    description: str = Field(..., min_length=1, max_length=500, description="Condition description")
    condition_type: ConditionType = Field(..., description="Type of condition")
    required_by_date: Optional[datetime] = Field(None, description="Date by which condition must be satisfied")


class ConditionUpdateRequest(BaseModel):
    status: ConditionStatus = Field(..., description="New status of the condition")
    satisfied_by: Optional[int] = Field(None, gt=0, description="User who satisfied the condition")


class ConditionResponse(BaseModel):
    id: int
    application_id: int
    lender_submission_id: Optional[int]
    description: str
    condition_type: ConditionType
    status: ConditionStatus
    required_by_date: Optional[datetime]
    satisfied_at: Optional[datetime]
    satisfied_by: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ConditionListResponse(BaseModel):
    conditions: List[ConditionResponse]


class MessageListResponse(BaseModel):
    messages: List[MessageResponse]
```