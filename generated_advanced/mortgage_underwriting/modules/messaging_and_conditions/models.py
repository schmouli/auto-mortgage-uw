from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Text, Numeric, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from mortgage_underwriting.common.database import Base

class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index('ix_messages_application_id', 'application_id'),
        Index('ix_messages_sender_id', 'sender_id'),
        Index('ix_messages_recipient_id', 'recipient_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="messages")
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_id])

class Condition(Base):
    __tablename__ = "conditions"
    __table_args__ = (
        Index('ix_conditions_application_id', 'application_id'),
        Index('ix_conditions_lender_submission_id', 'lender_submission_id'),
        Index('ix_conditions_status', 'status'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    lender_submission_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lender_submissions.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    condition_type: Mapped[str] = mapped_column(String(20), nullable=False)  # document/information/other
    status: Mapped[str] = mapped_column(String(20), default="outstanding", nullable=False)  # outstanding/satisfied/waived
    required_by_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    satisfied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    satisfied_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="conditions")
    lender_submission: Mapped["LenderSubmission"] = relationship("LenderSubmission", back_populates="conditions")
    satisfied_by_user: Mapped["User"] = relationship("User", foreign_keys=[satisfied_by])