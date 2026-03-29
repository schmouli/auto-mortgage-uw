from datetime import datetime
from sqlalchemy import Text, DateTime, Boolean, Date, ForeignKey, Index, func, or_
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from mortgage_underwriting.common.database import Base
from mortgage_underwriting.common.security import encrypt_pii, decrypt_pii

message_recipient_index = Index('ix_messages_recipient_id', 'recipient_id')
message_application_index = Index('ix_messages_application_id', 'application_id')


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    _body: Mapped[str] = mapped_column("body", Text, nullable=False)  # Encrypted field
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Security: Add audit fields
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)  # Track message creator

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", foreign_keys=[application_id], back_populates="messages")
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_id])

    @property
    def body(self) -> str:
        """Decrypt and return message body."""
        return decrypt_pii(self._body)

    @body.setter
    def body(self, value: str) -> None:
        """Encrypt message body before storage."""
        self._body = encrypt_pii(value)


condition_status_enum = ENUM('outstanding', 'satisfied', 'waived', name='condition_status_enum', create_type=False)
condition_type_enum = ENUM('document', 'information', 'other', name='condition_type_enum', create_type=False)


class Condition(Base):
    __tablename__ = "conditions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    lender_submission_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lender_submissions.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    condition_type: Mapped[str] = mapped_column(condition_type_enum, nullable=False)
    status: Mapped[str] = mapped_column(condition_status_enum, default='outstanding', nullable=False)  # FIXED: Corrected enum reference
    required_by_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    satisfied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    satisfied_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Security: Add audit fields for compliance
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)  # Track condition creator

    # Audit trail for status changes (FINTRAC compliance)
    status_history: Mapped[str] = mapped_column(Text, nullable=True)  # JSON string tracking status changes

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", foreign_keys=[application_id], back_populates="conditions")
    lender_submission: Mapped["LenderSubmission"] = relationship("LenderSubmission", foreign_keys=[lender_submission_id])
    satisfied_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[satisfied_by])