from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class MessageBase(BaseModel):
    application_id: int = Field(..., gt=0)
    sender_id: int = Field(..., gt=0)
    recipient_id: int = Field(..., gt=0)
    body: str = Field(..., min_length=1, max_length=5000)


class MessageCreate(MessageBase):
    pass


class MessageUpdateRead(BaseModel):
    is_read: bool = Field(True, description="Mark message as read")


class MessageResponse(MessageBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_read: bool
    sent_at: datetime
    read_at: Optional[datetime] = None
    created_at: datetime


class MessageQueryParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number (starting at 1)")
    limit: int = Field(20, ge=1, le=100, description="Items per page (max 100)")
    sender_id: Optional[int] = Field(None, gt=0)
    recipient_id: Optional[int] = Field(None, gt=0)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    is_read: Optional[bool] = None


class ConditionBase(BaseModel):
    application_id: int = Field(..., gt=0)
    lender_submission_id: Optional[int] = Field(None, gt=0)
    description: str = Field(..., min_length=1, max_length=2000)
    condition_type: str = Field(..., pattern="^(document|information|other)$")
    required_by_date: Optional[date] = None


class ConditionCreate(ConditionBase):
    pass


class ConditionStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(outstanding|satisfied|waived)$")
    satisfied_by: Optional[int] = Field(None, gt=0, description="Required when setting status to satisfied")


class ConditionResponse(ConditionBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    status: str
    satisfied_at: Optional[datetime] = None
    satisfied_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class PaginatedMessageResponse(BaseModel):
    messages: List[MessageResponse]
    total: int
    page: int
    limit: int


class PaginatedConditionResponse(BaseModel):
    conditions: List[ConditionResponse]
    total: int
    page: int
    limit: int