from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Boolean, Text, Integer, Numeric, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from typing import Optional, Dict, Any

from mortgage_underwriting.common.database import Base


class ScheduledJob(Base):
    """Scheduled background job configuration."""
    __tablename__ = "scheduled_jobs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    schedule: Mapped[str] = mapped_column(String(100), nullable=False)  # Cron expression
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    last_run: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_run: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_scheduled_jobs_enabled_next_run', 'enabled', 'next_run'),
    )


class JobExecutionLog(Base):
    """Immutable log of job executions."""
    __tablename__ = "job_execution_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    execution_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)  # UUID
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # queued, running, completed, failed
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_job_execution_logs_job_name_created_at', 'job_name', 'created_at'),
        Index('ix_job_execution_logs_status', 'status'),
    )