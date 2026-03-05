from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, Boolean,
    ForeignKey, Text, CheckConstraint, Index, func
)
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from decimal import Decimal
from datetime import datetime
from typing import List, Optional

from mortgage_underwriting.common.database import Base


class UnderwritingRule(Base):
    __tablename__ = "underwriting_rules"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # FIXED: Added updated_at field


class UnderwritingApplication(Base):
    __tablename__ = "underwriting_applications"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)  # FIXED: Added ondelete parameter
    
    # Financial inputs
    gross_monthly_income: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2))
    property_tax_monthly: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2))
    heating_cost_monthly: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2))
    condo_fee_monthly: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=10, scale=2), nullable=True)
    total_debts_monthly: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2))
    property_price: Mapped[Decimal] = mapped_column(Numeric(precision=19, scale=4))  # FIXED: Changed to Numeric(19,4)
    down_payment: Mapped[Decimal] = mapped_column(Numeric(precision=19, scale=4))  # FIXED: Changed to Numeric(19,4)
    contract_rate: Mapped[Decimal] = mapped_column(Numeric(precision=6, scale=4))
    
    # Results
    qualifies: Mapped[bool] = mapped_column(Boolean, default=False)
    decision: Mapped[str] = mapped_column(String(20))
    
    gds_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=5, scale=4), nullable=True)
    tds_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=5, scale=4), nullable=True)
    ltv_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=6, scale=4), nullable=True)
    cmhc_required: Mapped[bool] = mapped_column(Boolean, default=False)
    cmhc_premium_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=14, scale=2), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # FIXED: Added updated_at field
    
    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="applications")  # FIXED: Added type annotation
    decline_reasons: Mapped[List["DeclineReason"]] = relationship("DeclineReason", back_populates="application")  # FIXED: Added type parameter
    conditions: Mapped[List["Condition"]] = relationship("Condition", back_populates="application")  # FIXED: Added type parameter
    overrides: Mapped[List["OverrideRecord"]] = relationship("OverrideRecord", back_populates="application")


class UnderwritingDecision(Base):
    __tablename__ = "underwriting_decisions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriting_applications.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)  # APPROVED, CONDITIONAL, DECLINED
    decision_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    application: Mapped["UnderwritingApplication"] = relationship("UnderwritingApplication", back_populates="decisions")
    
    __table_args__ = (
        Index('ix_application_status', 'application_id', 'status'),  # FIXED: Added composite index
    )


class DeclineReason(Base):
    __tablename__ = "decline_reasons"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriting_applications.id"))
    reason_code: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    application: Mapped["UnderwritingApplication"] = relationship("UnderwritingApplication", back_populates="decline_reasons")


class Condition(Base):
    __tablename__ = "conditions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriting_applications.id"))
    condition_text: Mapped[str] = mapped_column(Text)
    is_met: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    application: Mapped["UnderwritingApplication"] = relationship("UnderwritingApplication", back_populates="conditions")


class OverrideRecord(Base):
    __tablename__ = "override_records"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriting_applications.id"))
    overridden_by: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(Text)
    override_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    application: Mapped["UnderwritingApplication"] = relationship("UnderwritingApplication", back_populates="overrides")
```

```