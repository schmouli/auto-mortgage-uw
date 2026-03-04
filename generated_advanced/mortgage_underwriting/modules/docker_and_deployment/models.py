```python
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Boolean,
    Text,
    Integer,
    CheckConstraint,
    Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.sql import func
from common.database import Base


class Deployment(Base, AsyncAttrs):
    __tablename__ = "deployments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    environment: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint("environment IN ('development', 'staging', 'production')"),
        nullable=False
    )
    version: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    changed_by: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Relationships
    services: Mapped[list["Service"]] = relationship("Service", back_populates="deployment")
    
    __table_args__ = (
        Index('idx_deployment_env', 'environment'),
        Index('idx_deployment_name', 'name')
    )


class Service(Base, AsyncAttrs):
    __tablename__ = "services"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deployment_id: Mapped[int] = mapped_column(ForeignKey("deployments.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., backend, frontend, etc.
    image_tag: Mapped[str] = mapped_column(String(100), nullable=False)
    container_port: Mapped[int] = mapped_column(Integer)
    replicas: Mapped[int] = mapped_column(Integer, default=1)
    cpu_limit: Mapped[Decimal] = mapped_column(Decimal(5, 2))  # CPU cores limit
    memory_limit_mb: Mapped[Decimal] = mapped_column(Decimal(10, 2))  # Memory in MB
    
    # Health check configuration
    health_check_path: Mapped[Optional[str]] = mapped_column(String(200))
    health_check_interval_sec: Mapped[int] = mapped_column(Integer, default=30)
    health_check_timeout_sec: Mapped[int] = mapped_column(Integer, default=10)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    changed_by: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Relationships
    deployment: Mapped["Deployment"] = relationship("Deployment", back_populates="services")
    configurations: Mapped[list["ServiceConfiguration"]] = relationship("ServiceConfiguration", back_populates="service")
    
    __table_args__ = (
        Index('idx_service_deployment', 'deployment_id'),
        Index('idx_service_name', 'name')
    )


class ServiceConfiguration(Base, AsyncAttrs):
    __tablename__ = "service_configurations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False)
    config_key: Mapped[str] = mapped_column(String(100), nullable=False)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    changed_by: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Relationships
    service: Mapped["Service"] = relationship("Service", back_populates="configurations")
    
    __table_args__ = (
        Index('idx_config_service', 'service_id'),
        Index('idx_config_key', 'config_key')
    )
```