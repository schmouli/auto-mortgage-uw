from datetime import datetime
from decimal import Decimal
from sqlalchemy import Index, Numeric, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class UnderwritingResult(Base):
    """Underwriting result with regulatory compliance tracking."""

    __tablename__ = "underwriting_results"
    __table_args__ = (
        Index('ix_uw_client_id', 'client_id'),
        Index('ix_uw_application_id', 'application_id'),
        Index('ix_uw_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    application_id: Mapped[Optional[int]] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="SET NULL"))
    
    # Ratios and Calculations
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)  # e.g., 0.3512 for 35.12%
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    qualifying_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)  # Stress test rate
    max_mortgage_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    
    # CMHC Insurance
    cmhc_required: Mapped[bool] = mapped_column(Boolean, default=False)
    cmhc_premium_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    cmhc_premium_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    
    # Decision
    qualifies: Mapped[bool] = mapped_column(Boolean, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # APPROVED, CONDITIONAL, DECLINED
    decline_reasons: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of reasons
    conditions: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of conditions
    stress_test_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    
    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="underwriting_results")  # From client module
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="underwriting_result")  # From application module


class UnderwritingOverride(Base):
    """Admin override record for underwriting decisions."""

    __tablename__ = "underwriting_overrides"
    __table_args__ = (
        Index('ix_override_result_id', 'underwriting_result_id'),
        Index('ix_override_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    underwriting_result_id: Mapped[int] = mapped_column(ForeignKey("underwriting_results.id", ondelete="CASCADE"), nullable=False)
    overridden_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    previous_decision: Mapped[str] = mapped_column(String(20), nullable=False)
    new_decision: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationship
    underwriting_result: Mapped["UnderwritingResult"] = relationship("UnderwritingResult", back_populates="overrides")


# Add back_populates to Client and MortgageApplication if needed
# In Client model (from client module):
# underwriting_results: Mapped[List["UnderwritingResult"]] = relationship("UnderwritingResult", back_populates="client")
#
# In MortgageApplication model (from application module):
# underwriting_result: Mapped["UnderwritingResult"] = relationship("UnderwritingResult", back_populates="application")

UnderwritingResult.overrides = relationship("UnderwritingOverride", back_populates="underwriting_result")