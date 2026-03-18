from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, Numeric, Boolean, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional, Dict, Any
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base
import json

class ReportCache(Base):
    """Cache layer for expensive report queries to improve performance."""
    __tablename__ = "report_cache"
    __table_args__ = (
        Index('ix_report_cache_type_period', 'report_type', 'period'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # pipeline/volume/lender
    period: Mapped[str] = mapped_column(String(20), nullable=False)  # ISO date range or 'monthly'/'ytd'
    filters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON-encoded filter dict
    data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON-encoded result
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def set_filters(self, filter_dict: Dict[str, Any]) -> None:
        self.filters = json.dumps(filter_dict)

    def set_data(self, data_dict: Dict[str, Any]) -> None:
        self.data = json.dumps(data_dict)

class FintracReportSummary(Base):
    """FINTRAC compliance summary for regulatory reporting.
    
    Tracks high-value transactions and PIPEDA compliance.
    """
    __tablename__ = "fintrac_report_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    total_transactions: Mapped[int] = mapped_column(Integer, default=0)
    high_value_count: Mapped[int] = mapped_column(Integer, default=0)  # >$10k
    sin_compliance_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal('0.0'))  # Percentage
    audit_trail_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('ix_fintrac_summary_month', 'report_month'),
    )