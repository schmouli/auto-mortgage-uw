from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, Integer, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class ScheduledJobExecution(Base):
    """Track execution history of scheduled background jobs.
    
    Complies with FINTRAC 5-year retention and audit requirements.
    """
    __tablename__ = "scheduled_job_executions"
    __table_args__ = (
        Index('ix_scheduled_job_executions_task_name', 'task_name'),
        Index('ix_scheduled_job_executions_status', 'status'),
        Index('ix_scheduled_job_executions_started_at', 'started_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)  # UUID
    task_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # pending, running, success, failed, retry
    args: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON serialized (PII redacted)
    kwargs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON serialized (PII redacted)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    runtime_seconds: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)  # FIXED: Changed to Numeric for financial precision
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # FIXED: Ensured timezone=True
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # FIXED: Ensured timezone=True
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())  # FIXED: Ensured timezone=True
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # FIXED: Ensured timezone=True