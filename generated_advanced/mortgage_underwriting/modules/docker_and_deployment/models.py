from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Text, DateTime, Integer, Numeric, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base


class DeploymentStrategyEnum(SQLEnum):
    ROLLING = "rolling"
    BLUE_GREEN = "blue-green"
    RECREATE = "recreate"


class ServiceStatusEnum(SQLEnum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    PENDING = "pending"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class DeploymentStatusEnum(SQLEnum):
    PENDING = "pending"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    strategy: Mapped[str] = mapped_column(SQLEnum(DeploymentStrategyEnum), nullable=False)
    status: Mapped[str] = mapped_column(SQLEnum(DeploymentStatusEnum), default="pending", nullable=False)
    logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ServiceHealthCheck(Base):
    __tablename__ = "service_health_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(SQLEnum(ServiceStatusEnum), nullable=False)
    latency_ms: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())