from datetime import datetime
from decimal import Decimal
from sqlalchemy import Index, String, Boolean, DateTime, ForeignKey, Text, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base

class ClientPortalUser(Base):
    """User account for client portal access."""
    __tablename__ = "client_portal_users"
    __table_args__ = (
        Index('ix_client_portal_users_user_id', 'user_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'client' or 'broker'
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="client_portal_user")


class Notification(Base):
    """In-app notification system for clients and brokers."""
    __tablename__ = "notifications"
    __table_args__ = (
        Index('ix_notifications_recipient_id', 'recipient_id'),
        Index('ix_notifications_is_read', 'is_read'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recipient_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., document_uploaded, status_changed
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    recipient: Mapped["User"] = relationship("User", back_populates="notifications")


class User(Base):
    """Core user entity shared across modules."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    client_portal_user: Mapped[Optional["ClientPortalUser"]] = relationship("ClientPortalUser", back_populates="user", uselist=False)
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="recipient", cascade="all, delete-orphan")