from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, Index, Numeric
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base

class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)  # UUID
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="submitted")
    deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    audit_logs: Mapped[list["DeploymentAuditLog"]] = relationship("DeploymentAuditLog", back_populates="deployment")

class DeploymentAuditLog(Base):
    __tablename__ = "deployment_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    deployment_id: Mapped[int] = mapped_column(Integer, ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    deployment: Mapped["Deployment"] = relationship("Deployment", back_populates="audit_logs")

Index("idx_deployments_application_id", Deployment.application_id)