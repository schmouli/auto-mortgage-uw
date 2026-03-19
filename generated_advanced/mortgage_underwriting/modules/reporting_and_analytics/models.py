from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from mortgage_underwriting.common.database import Base


class ReportCache(Base):
    """Precomputed report data cached for performance."""
    __tablename__ = "report_caches"
    __table_args__ = (
        Index('ix_report_cache_report_type', 'report_type'),
        Index('ix_report_cache_period_start', 'period_start'),
        Index('ix_report_cache_period_end', 'period_end'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # pipeline, volume, lender
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Audit Fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class FintracReportSummary(Base):
    """FINTRAC compliance summary snapshot."""
    __tablename__ = "fintrac_report_summaries"
    __table_args__ = (
        Index('ix_fintrac_summary_generated_date', 'generated_date'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    generated_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    total_transactions: Mapped[int] = mapped_column(Integer, nullable=False)
    flagged_count: Mapped[int] = mapped_column(Integer, nullable=False)
    high_risk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    compliance_notes: Mapped[Optional[str]] = mapped_column(Text)
    data_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Audit Fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)