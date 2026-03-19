from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, ForeignKey, Numeric, Text, Boolean, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional, List

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class UnderwritingResult(Base):
    __tablename__ = "underwriting_results"
    __table_args__ = (
        CheckConstraint("gds_ratio <= 0.39", name="check_gds_max"),
        CheckConstraint("tds_ratio <= 0.44", name="check_tds_max"),
        Index("ix_uw_result_application_id", "application_id"),
        Index("ix_uw_result_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    qualifies: Mapped[bool] = mapped_column(Boolean, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # APPROVED, CONDITIONAL, DECLINED
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    cmhc_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cmhc_premium_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    qualifying_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    max_mortgage: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    decline_reasons: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    conditions: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    stress_test_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="underwriting_results")


class UnderwritingOverride(Base):
    __tablename__ = "underwriting_overrides"
    __table_args__ = (
        Index("ix_override_result_id", "result_id"),
        Index("ix_override_created_by", "created_by"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("underwriting_results.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    result: Mapped["UnderwritingResult"] = relationship("UnderwritingResult", back_populates="overrides")

UnderwritingResult.overrides = relationship("UnderwritingOverride", back_populates="result", cascade="all, delete-orphan")