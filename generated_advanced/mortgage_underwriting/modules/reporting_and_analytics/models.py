from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, Index, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional

from mortgage_underwriting.common.database import Base


class ReportCache(Base):
    """Caches pre-computed report data for performance.
    
    Used to avoid expensive joins/calculations on live data.
    Refreshed via background job every 4 hours or on demand.
    """
    __tablename__ = "report_cache"
    __table_args__ = (
        Index('ix_report_cache_report_type_period', 'report_type', 'period_start', 'period_end'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # pipeline/volume/lender
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string of computed metrics
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class FintracReportEntry(Base):
    """Tracks report generation for FINTRAC compliance audits.
    
    Immutable log of all report exports with user, filters, and timestamp.
    Retention: 5 years (managed by cleanup job).
    """
    __tablename__ = "fintrac_report_entries"
    __table_args__ = (
        Index('ix_fintrac_report_user_id', 'user_id'),
        Index('ix_fintrac_report_generated_at', 'generated_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)  # fintrac_summary, export_csv
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON of query params used
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # if exported
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", uselist=False)