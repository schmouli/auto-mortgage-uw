from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean, Text, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base

class ClientPortalActivity(Base):
    """Immutable audit trail for client portal activities."""
    __tablename__ = "client_portal_activities"
    __table_args__ = (
        Index('ix_client_portal_activities_user_id', 'user_id'),
        Index('ix_client_portal_activities_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # login, view_application, upload_document, etc.
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 compatible
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON serialized additional info
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="portal_activities")


class Notification(Base):
    """In-app notifications for users."""
    __tablename__ = "notifications"
    __table_args__ = (
        Index('ix_notifications_user_id', 'user_id'),
        Index('ix_notifications_is_read', 'is_read'),
        Index('ix_notifications_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)  # document_uploaded, status_changed, etc.
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g., document ID or application ID
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")


class UserPreference(Base):
    """User-specific preferences for the portal interface."""
    __tablename__ = "user_preferences"
    __table_args__ = (
        Index('ix_user_preferences_user_id', 'user_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    email_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    in_app_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    dashboard_layout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON layout configuration
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="preference")