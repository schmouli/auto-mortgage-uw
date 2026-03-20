from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base

class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index('ix_messages_application_id', 'application_id'),
        Index('ix_messages_sender_id', 'sender_id'),
        Index('ix_messages_recipient_id', 'recipient_id'),
        Index('ix_messages_sent_at', 'sent_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    message_type: Mapped[str] = mapped_column(String(20), default="internal", nullable=False)  # internal, external, system

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)  # FIXED: Added missing updated_at field


class Condition(Base):
    __tablename__ = "conditions"
    __table_args__ = (
        Index('ix_conditions_application_id', 'application_id'),
        Index('ix_conditions_lender_submission_id', 'lender_submission_id'),
        Index('ix_conditions_status', 'status'),
        Index('ix_conditions_required_by_date', 'required_by_date'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False)
    lender_submission_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lender_submissions.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    condition_type: Mapped[str] = mapped_column(String(20), nullable=False)  # document, information, other
    status: Mapped[str] = mapped_column(String(20), default="outstanding", nullable=False)  # outstanding, satisfied, waived
    required_by_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    satisfied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    satisfied_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)