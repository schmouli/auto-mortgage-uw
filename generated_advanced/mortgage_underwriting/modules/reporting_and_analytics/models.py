from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean, Text, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any

from mortgage_underwriting.common.database import Base

class ReportCache(Base):
    """Caches expensive report queries for faster retrieval.
    
    Used to prevent repeated computation of aggregations over large datasets.
    Cache invalidated by scheduled jobs or manual triggers.
    """

    __tablename__ = "report_caches"
    __table_args__ = (
        Index('ix_report_cache_report_type_period', 'report_type', 'period_start', 'period_end'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # 'pipeline', 'volume', 'lender'
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cached_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FintracReport(Base):
    """Tracks high-value transactions for FINTRAC compliance reporting.
    
    Maintains immutable record of flagged transactions >$10K.
    Used for generating regulatory summaries and audit trails.
    """

    __tablename__ = "fintrac_reports"
    __table_args__ = (
        Index('ix_fintrac_report_transaction_date', 'transaction_date'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    transaction_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'purchase', 'refinance', etc.
    is_high_value: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    flagged_reason: Mapped[Optional[str]] = mapped_column(String(200))
    reported_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="fintrac_report")
    client: Mapped["Client"] = relationship("Client")