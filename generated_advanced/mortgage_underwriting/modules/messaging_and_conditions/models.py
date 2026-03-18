from datetime import datetime
from sqlalchemy import Text, DateTime, ForeignKey, Boolean, Index, func, Integer, String
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from mortgage_underwriting.common.database import Base


class MessageType(str, ENUM):
    DOCUMENT_REQUEST = "document_request"
    INFORMATION_REQUEST = "information_request"
    GENERAL = "general"


class ConditionStatus(str, ENUM):
    OUTSTANDING = "outstanding"
    SATISFIED = "satisfied"
    WAIVED = "waived"


class ConditionType(str, ENUM):
    DOCUMENT = "document"
    INFORMATION = "information"
    OTHER = "other"


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index('idx_messages_application_id', 'application_id'),
        Index('idx_messages_recipient_id', 'recipient_id'),
        Index('idx_messages_sender_id', 'sender_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    recipient_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="messages")
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_id])


class Condition(Base):
    __tablename__ = "conditions"
    __table_args__ = (
        Index('idx_conditions_application_id', 'application_id'),
        Index('idx_conditions_status', 'status'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    lender_submission_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("lender_submissions.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    condition_type: Mapped[ConditionType] = mapped_column(ENUM(ConditionType), nullable=False)
    status: Mapped[ConditionStatus] = mapped_column(ENUM(ConditionStatus), default=ConditionStatus.OUTSTANDING, nullable=False)
    required_by_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    satisfied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    satisfied_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="conditions")
    lender_submission: Mapped["LenderSubmission"] = relationship("LenderSubmission", back_populates="conditions")
    satisfied_by_user: Mapped["User"] = relationship("User", foreign_keys=[satisfied_by])