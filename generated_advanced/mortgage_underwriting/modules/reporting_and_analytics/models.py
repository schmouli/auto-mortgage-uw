from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey, Boolean, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from mortgage_underwriting.common.database import Base


class ReportCache(Base):
    """Cache for pre-computed reports to improve performance."""
    __tablename__ = "report_caches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # pipeline, volume, lender
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    filters: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # JSON filter criteria
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)  # Cached report data
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_expired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index('ix_report_cache_type_period', 'report_type', 'period_start', 'period_end'),
    )


class FintracReportSummary(Base):
    """FINTRAC compliance reporting summary for regulatory audits.
    
    Tracks transaction monitoring and large cash reporting compliance.
    Maintains immutable record of compliance checks performed.
    """
    __tablename__ = "fintrac_report_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    total_transactions: Mapped[int] = mapped_column(Integer, nullable=False)
    high_value_transactions: Mapped[int] = mapped_column(Integer, nullable=False)  # >$10k
    flagged_for_review: Mapped[int] = mapped_column(Integer, nullable=False)
    compliance_status: Mapped[str] = mapped_column(String(50), nullable=False)  # COMPLIANT, REVIEW_REQUIRED, NON_COMPLIANT
    summary_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index('ix_fintrac_summary_date', 'report_date'),
    )


class ReportExportLog(Base):
    """Log of all report exports for audit trail purposes.
    
    Required for FINTRAC and internal compliance tracking.
    Records who exported what, when, and in what format.
    """
    __tablename__ = "report_export_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    export_format: Mapped[str] = mapped_column(String(20), nullable=False)  # CSV, PDF, JSON
    export_filters: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    export_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationship
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index('ix_report_export_user', 'user_id'),
        Index('ix_report_export_type', 'report_type'),
    )