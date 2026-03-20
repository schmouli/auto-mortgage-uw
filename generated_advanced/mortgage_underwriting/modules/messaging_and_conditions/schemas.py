from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

# Message Schemas

class MessageLookupRequest(BaseModel):
    cursor: Optional[datetime] = None
    limit: int = Field(default=50, le=200, gt=0)
    is_read: Optional[bool] = None
    message_type: Optional[str] = Field(None, pattern="^(internal|external|system)$")


class MessageCreateRequest(BaseModel):
    recipient_id: int = Field(..., description="Recipient user ID (must be participant in application)")
    body: str = Field(..., min_length=1, max_length=5000, description="Message body")
    message_type: str = Field(default="internal", pattern="^(internal|external|system)$", description="Message type")


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    # FIXED: Removed extra fields to match model exactly
    id: int
    application_id: int
    sender_id: int
    recipient_id: int
    body: str
    is_read: bool
    sent_at: datetime
    read_at: Optional[datetime]
    message_type: str
    created_at: datetime


class MessageThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    messages: List[MessageResponse]
    next_cursor: Optional[datetime]
    total_count: int


# Condition Schemas

class ConditionCreateRequest(BaseModel):
    lender_submission_id: Optional[int] = None
    description: str = Field(..., min_length=1, max_length=2000)
    condition_type: str = Field(..., pattern="^(document|information|other)$")
    required_by_date: Optional[datetime] = None


class ConditionUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(outstanding|satisfied|waived)$")
    satisfied_at: Optional[datetime] = None
    satisfied_by: Optional[int] = None


class ConditionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    # FIXED: Reduced fields to essential subset to match expected schema
    id: int
    application_id: int
    description: str
    condition_type: str
    status: str
    required_by_date: Optional[datetime]
    satisfied_at: Optional[datetime]


class OutstandingConditionsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    conditions: List[ConditionResponse]
    total_count: int