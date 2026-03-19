from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import Integer, String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class ServiceHealth(Base):
    __tablename__ = "service_health"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # healthy/unhealthy
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SystemStatus(Base):
    __tablename__ = "system_status"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    overall_status: Mapped[str] = mapped_column(String(20), nullable=False)  # healthy/degraded/unavailable
    service_statuses: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    gpu_status: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())