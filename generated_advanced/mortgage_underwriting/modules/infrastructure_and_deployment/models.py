from datetime import datetime
from sqlalchemy import Index, Numeric, String, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from sqlalchemy.sql import func
from decimal import Decimal
from mortgage_underwriting.common.database import Base


class DeploymentStatus(Base):
    __tablename__ = "deployment_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deployment_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    service_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # pending, deploying, success, failed, rolled_back
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_deployment_service', 'deployment_id', 'service_name'),
    )


class HealthCheckResult(Base):
    __tablename__ = "health_check_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # healthy, degraded, unhealthy
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)  # FIXED: Changed from int to Decimal to match Numeric column type
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_health_service_time', 'service_name', 'checked_at'),
    )