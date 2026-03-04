```python
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, Boolean,
    ForeignKey, Text, CheckConstraint, Index
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from decimal import Decimal
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.db.base_class import Base


class UnderwritingApplication(Base):
    __tablename__ = "underwriting_applications"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    
    # Financial inputs
    gross_monthly_income: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2))
    property_tax_monthly: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2))
    heating_cost_monthly: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2))
    condo_fee_monthly: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=10, scale=2), nullable=True)
    total_debts_monthly: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2))
    property_price: Mapped[Decimal] = mapped_column(Numeric(precision=14, scale=2))
    down_payment: Mapped[Decimal] = mapped_column(Numeric(precision=14, scale=2))
    contract_rate: Mapped[Decimal] = mapped_column(Numeric(precision=6, scale=4))
    
    # Results
    qualifies: Mapped[bool] = mapped_column(Boolean, default=False)
    decision: Mapped[str] = mapped_column(String(20))  # APPROVED, CONDITIONAL, DECLINED
    
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=4), nullable=True)
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=4), nullable=True)
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(precision=6, scale=4), nullable=True)
    cmhc_required: Mapped[bool] = mapped_column(Boolean, default=False)
    cmhc_premium_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=12, scale=2), nullable=True)
    qualifying_rate: Mapped[Decimal] = mapped_column(Numeric(precision=6, scale=4), nullable=True)
    max_mortgage: Mapped[Decimal] = mapped_column(Numeric(precision=14, scale=2), nullable=True)
    
    decline_reasons: Mapped[List['DeclineReason']] = relationship(
        "DeclineReason", back_populates="application", cascade="all, delete-orphan"
    )
    conditions: Mapped[List['Condition']] = relationship(
        "Condition", back_populates="application", cascade="all, delete-orphan"
    )
    
    stress_test_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    changed_by: Mapped[str] = mapped_column(String(100))
    
    __table_args__ = (
        CheckConstraint('decision IN (\'APPROVED\', \'CONDITIONAL\', \'DECLINED\')', name='valid_decision'),
        Index('ix_underwriting_application_id', 'application_id'),
    )


class DeclineReason(Base):
    __tablename__ = "decline_reasons"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriting_applications.id"), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    
    application: Mapped[UnderwritingApplication] = relationship("UnderwritingApplication", back_populates="decline_reasons")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Condition(Base):
    __tablename__ = "conditions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriting_applications.id"), nullable=False)
    condition_text: Mapped[str] = mapped_column(Text)
    is_met: Mapped[bool] = mapped_column(Boolean, default=False)
    
    application: Mapped[UnderwritingApplication] = relationship("UnderwritingApplication", back_populates="conditions")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OverrideRecord(Base):
    __tablename__ = "override_records"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriting_applications.id"), nullable=False)
    overridden_by: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```