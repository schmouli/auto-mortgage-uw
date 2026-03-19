from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, Text, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base

class ServiceHealth(Base):
    __tablename__ = "service_health"
    __table_args__ = (
        Index('ix_service_health_service_name', 'service_name'),
        Index('ix_service_health_timestamp', 'timestamp'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # healthy, degraded, unhealthy
    response_time_ms: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DeploymentLog(Base):
    __tablename__ = "deployment_logs"
    __table_args__ = (
        Index('ix_deployment_logs_service_name', 'service_name'),
        Index('ix_deployment_logs_status', 'status'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # deploying, deployed, failed
    initiated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deployment_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rollback_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())