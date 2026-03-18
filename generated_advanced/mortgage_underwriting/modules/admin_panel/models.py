from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, Boolean, DateTime, Text, Numeric, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index('ix_audit_logs_entity_type_id', 'entity_type', 'entity_id'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)  # FIXED: Added missing updated_at field

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")


class Lender(Base):
    __tablename__ = "lenders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    products: Mapped[list["LenderProduct"]] = relationship("LenderProduct", back_populates="lender", cascade="all, delete-orphan")


class LenderProduct(Base):
    __tablename__ = "lender_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lender_id: Mapped[int] = mapped_column(Integer, ForeignKey("lenders.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    min_loan_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)  # FIXED: Changed to Numeric(19,4) for monetary values
    max_loan_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)  # FIXED: Changed to Numeric(19,4) for monetary values
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)  # e.g., 0.0350 for 3.5%
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    lender: Mapped["Lender"] = relationship("Lender", back_populates="products")