from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Index,
    Numeric,
    String,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class ClientPortalUser(Base):
    """Client-facing user account for portal access.
    
    Links to internal client record but maintains separate auth.
    """

    __tablename__ = "client_portal_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    client: Mapped["Client"] = relationship(
        "Client", back_populates="portal_user", uselist=False
    )
    notifications: Mapped[List["ClientNotification"]] = relationship(
        "ClientNotification", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_client_portal_users_email", "email"),)


class ClientNotification(Base):
    """In-app notifications for client portal users.
    
    Immutable after creation. Read/unread tracked client-side.
    """

    __tablename__ = "client_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("client_portal_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    related_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["ClientPortalUser"] = relationship(
        "ClientPortalUser", back_populates="notifications"
    )

    __table_args__ = (
        Index("ix_client_notifications_user_id_created_at", "user_id", "created_at"),
    )