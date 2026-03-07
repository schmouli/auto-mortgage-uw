from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Index,
    Numeric,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class AuditLog(Base):
    """Immutable audit trail for compliance and debugging.

    Tracks all state changes across the system with who/when/what/why.
    Used for FINTRAC, OSFI B-20, and forensic analysis.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # CREATE, UPDATE, DELETE
    changed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    old_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_audit_logs_entity_type", "entity_type"),
        Index("ix_audit_logs_entity_id", "entity_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_changed_by", "changed_by"),
    )


class Lender(Base):
    """Financial institution offering mortgage products."""

    __tablename__ = "lenders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="lender", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_lenders_name", "name"),
        Index("ix_lenders_code", "code"),
        Index("ix_lenders_is_active", "is_active"),
    )


class Product(Base):
    """Mortgage product offered by a lender."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lender_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lenders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)  # e.g., 0.0525 for 5.25%
    max_ltv: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # e.g., 95.00 for 95%
    insurance_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
    lender: Mapped["Lender"] = relationship("Lender", back_populates="products")

    __table_args__ = (
        Index("ix_products_lender_id", "lender_id"),
        Index("ix_products_name", "name"),
        Index("ix_products_is_active", "is_active"),
    )