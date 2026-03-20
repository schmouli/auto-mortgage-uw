from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Boolean, Text, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from mortgage_underwriting.common.database import Base


class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        Index('ix_background_jobs_status', 'status'),
        Index('ix_background_jobs_scheduled_at', 'scheduled_at'),
        Index('ix_background_jobs_last_run_at', 'last_run_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    task_path: Mapped[str] = mapped_column(String(255), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    args_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, running, success, failed
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<BackgroundJob(id={self.id}, name='{self.name}', status='{self.status}')>"