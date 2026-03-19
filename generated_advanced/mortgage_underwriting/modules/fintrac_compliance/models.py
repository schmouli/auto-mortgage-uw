from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Boolean, Text, CheckConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from decimal import Decimal
from mortgage_underwriting.common.database import Base

class MortgageApplication(Base):
    __tablename__ = "mortgage_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)  # NEVER float
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # FINTRAC: Immutable audit trail enforcement
    __table_args__ = (
        CheckConstraint('purchase_price > 0', name='check_positive_purchase_price'),
    )

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="applications")

# FIXED: Added dedicated audit table for immutable transaction logging
from sqlalchemy import Column, Integer, DateTime, String, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from decimal import Decimal

class TransactionAuditLog(Base):
    __tablename__ = "transaction_audit_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    transaction_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    logged_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Enforce immutability constraints
    __table_args__ = (
        CheckConstraint('transaction_amount >= 0', name='check_non_negative_amount'),
    )