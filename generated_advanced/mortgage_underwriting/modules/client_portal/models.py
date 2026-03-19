from datetime import datetime
from typing import Optional

from sqlalchemy import (

    Integer, String, DateTime, ForeignKey, Numeric,
    Boolean, Text, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class ClientPortalAccess(Base):
    __tablename__ = "client_portal_access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="portal_access")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recipient_client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    recipient_broker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("brokers.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., document_uploaded, status_changed
    reference_id: Mapped[Optional[int]] = mapped_column(Integer)  # e.g., application_id
    reference_type: Mapped[Optional[str]] = mapped_column(String(50))  # e.g., Application
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    client_recipient: Mapped[Optional["Client"]] = relationship("Client", foreign_keys=[recipient_client_id], back_populates="notifications")
    broker_recipient: Mapped[Optional["Broker"]] = relationship("Broker", foreign_keys=[recipient_broker_id])


class DocumentUploadActivity(Base):
    __tablename__ = "document_upload_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    document_requirement_id: Mapped[int] = mapped_column(ForeignKey("document_requirements.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_kb: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="document_uploads")
    application: Mapped["Application"] = relationship("Application")
    document_requirement: Mapped["DocumentRequirement"] = relationship("DocumentRequirement")