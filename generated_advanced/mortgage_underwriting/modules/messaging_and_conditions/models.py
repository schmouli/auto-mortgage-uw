"""Messaging and Conditions module for mortgage underwriting system."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Boolean, Enum, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import StrEnum
from mortgage_underwriting.common.database import Base


class ConditionType(StrEnum):
    DOCUMENT = "document"
    INFORMATION = "information"
    OTHER = "other"


class ConditionStatus(StrEnum):
    OUTSTANDING = "outstanding"
    SATISFIED = "satisfied"
    WAIVED = "waived"


class Message(Base):
    __tablename__ = 'messages'
    __table_args__ = (
        Index('ix_message_is_read_recipient', 'is_read', 'recipient_id'),
        Index('ix_message_status_recipient', 'is_read', 'recipient_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey('applications.id'))
    sender_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    recipient_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    body: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id], viewonly=True)  # Type annotation added
    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_id], viewonly=True)


class Condition(Base):
    __tablename__ = 'conditions'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey('applications.id'))
    lender_submission_id: Mapped[Optional[int]] = mapped_column(ForeignKey('lender_submissions.id'), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    condition_type: Mapped[ConditionType] = mapped_column(Enum(ConditionType))
    status: Mapped[ConditionStatus] = mapped_column(Enum(ConditionStatus), default=ConditionStatus.OUTSTANDING)
    required_by_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    satisfied_by: Mapped[Optional[int]] = mapped_column(ForeignKey('users.id'), nullable=True)
    satisfied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    application: Mapped["Application"] = relationship("Application", viewonly=True)
    lender_submission: Mapped["LenderSubmission"] = relationship("LenderSubmission", viewonly=True)
```

```