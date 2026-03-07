from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, Boolean, Text, Numeric, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base

class DeploymentHealthCheck(Base):
    __tablename__ = "deployment_health_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # healthy, degraded, unhealthy
    version: Mapped[str] = mapped_column(String(50), nullable=True)
    uptime_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    details: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class DependencyHealth(Base):
    __tablename__ = "dependency_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deployment_id: Mapped[int] = mapped_column(Integer, ForeignKey("deployment_health_checks.id"), nullable=False, index=True)
    component_name: Mapped[str] = mapped_column(String(50), nullable=False)  # db, redis, minio
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # up, down
    latency_ms: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())