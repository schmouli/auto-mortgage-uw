from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from typing import List, Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base

class ServiceHealth(Base):
    __tablename__ = "service_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # healthy, unhealthy, degraded
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    last_check: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_service_health_name_last_check', 'service_name', 'last_check'),
    )

class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    triggered_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    services: Mapped[str] = mapped_column(Text, nullable=False)  # Comma-separated list
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # queued, deploying, success, failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_deployments_status_started', 'status', 'started_at'),
    )

class InfrastructureConfig(Base):
    __tablename__ = "infrastructure_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON configuration
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 hash
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_infra_config_service_deployed', 'service_name', 'deployed_at'),
    )