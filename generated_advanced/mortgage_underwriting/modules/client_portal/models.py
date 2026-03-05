from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Boolean, Text, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from decimal import Decimal
from typing import List
from mortgage_underwriting.common.database import Base


class Client(Base):
    __tablename__ = "clients"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    phone: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('ix_client_email', 'email'),
    )

    # Relationships
    sessions: Mapped[List["ClientPortalSession"]] = relationship(
        "ClientPortalSession",
        back_populates="client",
        lazy="selectin"
    )


class ClientPortalSession(Base):
    __tablename__ = "client_portal_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    ip_address: Mapped[str] = mapped_column(String(45))
    user_agent: Mapped[str] = mapped_column(Text)
    session_expiry_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2))  # Changed from Float to Numeric(5,2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # FIXED: Added updated_at field

    __table_args__ = (
        Index('ix_client_portal_session_client_is_active', 'client_id', 'is_active'),  # FIXED: Added composite index
    )

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="sessions")
```

```