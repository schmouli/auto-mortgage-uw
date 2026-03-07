from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Boolean, Text, Numeric, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base

class ServiceHealth(Base):
    __tablename__ = "service_health"
    __table_args__ = (
        Index('ix_service_health_name', 'name'),
        Index('ix_service_health_last_heartbeat', 'last_heartbeat'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    health_check_url: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # healthy, degraded, unhealthy
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[Optional[str]] = mapped_column(String(50))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    active_workflows: Mapped[Optional[int]] = mapped_column()
    response_time_ms: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class DeploymentStatus(Base):
    __tablename__ = "deployment_status"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # deployed, rolling_back, failed
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rollback_version: Mapped[Optional[str]] = mapped_column(String(50))
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ConfigValidation(Base):
    __tablename__ = "config_validations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    validator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    validation_errors: Mapped[Optional[str]] = mapped_column(Text)
    config_snapshot: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    validator: Mapped["User"] = relationship("User", back_populates="config_validations")

class SystemHealth(Base):
    __tablename__ = "system_health"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    overall_status: Mapped[str] = mapped_column(String(20), nullable=False)  # healthy, degraded, unhealthy
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())