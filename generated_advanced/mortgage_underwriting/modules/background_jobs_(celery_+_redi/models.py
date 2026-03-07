from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Boolean, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any

from mortgage_underwriting.common.database import Base

class JobExecutionLog(Base):
    """Immutable log of background job executions for audit and monitoring.
    
    Tracks all job runs including success/failure status, timing, and results.
    Used for operational monitoring and regulatory compliance (FINTRAC, OSFI).
    """
    __tablename__ = "job_execution_logs"
    __table_args__ = (
        Index('ix_job_execution_logs_task_name', 'task_name'),
        Index('ix_job_execution_logs_status', 'status'),
        Index('ix_job_execution_logs_scheduled_at', 'scheduled_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # pending, running, success, failure, retry
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    args: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    kwargs: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    is_manual_trigger: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    triggered_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    trigger_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[triggered_by])

class ScheduledJob(Base):
    """Configuration for recurring background jobs.
    
    Stores cron expressions and metadata for automated tasks.
    """
    __tablename__ = "scheduled_jobs"
    __table_args__ = (
        Index('ix_scheduled_jobs_is_active', 'is_active'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)