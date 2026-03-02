```python
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Numeric, func, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum

from app.db.base_class import Base
from app.models.user import User
from app.models.client import Client
from app.models.application import Application


class VerificationMethod(str, Enum):
    IN_PERSON = "in_person"
    CREDIT_FILE = "credit_file"
    DUAL_PROCESS = "dual_process"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReportType(str, Enum):
    LARGE_CASH_TRANSACTION = "large_cash_transaction"
    SUSPICIOUS_TRANSACTION = "suspicious_transaction"
    TERRORIST_PROPERTY = "terrorist_property"


class FintracVerification(Base):
    __tablename__ = "fintrac_verifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    
    verification_method: Mapped[VerificationMethod] = mapped_column(String(50), nullable=False)
    id_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., passport, driver's license
    id_number_encrypted: Mapped[str] = mapped_column(String(255), nullable=False)  # Encrypted storage
    id_expiry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_issuing_province: Mapped[Optional[str]] = mapped_column(String(100))
    
    verified_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    is_pep: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # High Impact Organization
    risk_level: Mapped[RiskLevel] = mapped_column(String(20), default=RiskLevel.LOW, nullable=False)
    
    record_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship("Application", foreign_keys=[application_id])
    client: Mapped["Client"] = relationship("Client", foreign_keys=[client_id])
    verifier: Mapped["User"] = relationship("User", foreign_keys=[verified_by])

    __table_args__ = (
        Index('ix_fintrac_verifications_client_id', 'client_id'),
        Index('ix_fintrac_verifications_application_id', 'application_id'),
        Index('ix_fintrac_verifications_verified_at', 'verified_at'),
    )


class FintracReport(Base):
    __tablename__ = "fintrac_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False)
    report_type: Mapped[ReportType] = mapped_column(String(50), nullable=False)
    
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=19, scale=2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CAD", nullable=False)  # ISO 4217 currency code
    
    report_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_to_fintrac_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fintrac_reference_number: Mapped[Optional[str]] = mapped_column(String(100))
    
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    application: Mapped["Application"] = relationship("Application", foreign_keys=[application_id])
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index('ix_fintrac_reports_application_id', 'application_id'),
        Index('ix_fintrac_reports_report_date', 'report_date'),
        Index('ix_fintrac_reports_submitted_to_fintrac_at', 'submitted_to_fintrac_at'),
    )
```