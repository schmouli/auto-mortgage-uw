from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_validator

# Message Schemas

class MessageBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    body: str = Field(..., min_length=1, max_length=5000)
    recipient_id: int = Field(..., gt=0)

class MessageCreate(MessageBase):
    pass

class MessageUpdateRead(BaseModel):
    is_read: bool = True

class MessageResponse(MessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    sender_id: int
    is_read: bool
    sent_at: datetime
    read_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

# Condition Schemas

class ConditionBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description: str = Field(..., min_length=1, max_length=2000)
    condition_type: str = Field(..., pattern="^(document|information|other)$")
    required_by_date: Optional[datetime] = None

    @field_validator('description')
    def validate_description(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Description cannot be empty or whitespace only')
        return v

class ConditionCreate(ConditionBase):
    pass

class ConditionUpdateStatus(BaseModel):
    status: str = Field(..., pattern="^(outstanding|satisfied|waived)$")
    satisfied_by: Optional[int] = None

class ConditionResponse(ConditionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    lender_submission_id: Optional[int] = None
    status: str
    satisfied_at: Optional[datetime] = None
    satisfied_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

# Pagination

class PaginatedMessagesResponse(BaseModel):
    items: List[MessageResponse]
    total: int
    page: int
    per_page: int

class PaginatedConditionsResponse(BaseModel):
    items: List[ConditionResponse]
    total: int
    page: int
    per_page: int