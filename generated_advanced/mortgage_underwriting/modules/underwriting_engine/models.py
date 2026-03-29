from datetime import datetime
from decimal import Decimal
from sqlalchemy import Index, Numeric, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class UnderwritingResult(Base):
    __tablename__ = "underwriting_results"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Ratios
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    
    # Qualification
    qualifies: Mapped[bool] = mapped_column(Boolean, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # APPROVED, CONDITIONAL, DECLINED
    
    # Financials
    qualifying_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_mortgage: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    
    # Insurance
    cmhc_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cmhc_premium_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    cmhc_premium_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    
    # Metadata
    decline_reasons: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stress_test_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="underwriting_result")
    client: Mapped["Client"] = relationship("Client", back_populates="underwriting_results")
    
    __table_args__ = (
        Index('ix_uw_result_app_id', 'application_id'),
        Index('ix_uw_result_client_id', 'client_id'),
    )


class UnderwritingOverride(Base):
    __tablename__ = "underwriting_overrides"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("underwriting_results.id", ondelete="CASCADE"), nullable=False, index=True)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    result: Mapped["UnderwritingResult"] = relationship("UnderwritingResult", back_populates="overrides")
    
    __table_args__ = (
        Index('ix_uw_override_result_id', 'result_id'),
    )


# Add to existing Client model in client/models.py
# underwriting_results: Mapped[List["UnderwritingResult"]] = relationship("UnderwritingResult", back_populates="client", cascade="all, delete-orphan")