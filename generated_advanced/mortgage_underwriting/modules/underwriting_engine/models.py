from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, ForeignKey, Numeric, Boolean, Text, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base

class UnderwritingResult(Base):
    __tablename__ = "underwriting_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    qualifies: Mapped[bool] = mapped_column(Boolean, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # APPROVED, CONDITIONAL, DECLINED
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    cmhc_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cmhc_premium_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    qualifying_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_mortgage: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    stress_test_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    decline_reasons: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="underwriting_result")
    client: Mapped["Client"] = relationship("Client", back_populates="underwriting_results")


Index('ix_underwriting_client_decision', UnderwritingResult.client_id, UnderwritingResult.decision)