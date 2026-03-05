from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Numeric, func, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum

from mortgage_underwriting.common.database import Base


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
    is_hio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(String(20), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(time0=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="fintrac_verifications")
    client: Mapped["Client"] = relationship("Client", back_populates="fintrac_verifications")
    verifier: Mapped["User"] = relationship("User", back_populates="fintrac_verifications")
    
    __table_args__ = (
        Index('ix_fintrac_verification_client_verified', 'client_id', 'verified_at'),
    )


class FintracReport(Base):
    __tablename__ = "fintrac_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    application_id: Mapped[Optional[int]] = mapped_column(ForeignKey("applications.id"))
    
    report_type: Mapped[ReportType] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)  # FIXED: Changed from Float to Decimal(19, 4)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CAD")
    report_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    is_submitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    submission_reference: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="fintrac_reports")
    application: Mapped["Application"] = relationship("Application", back_populates="fintrac_reports")
    creator: Mapped["User"] = relationship("User", back_populates="fintrac_reports")
    
    # FIXED: Added composite index for common query pattern
    __table_args__ = (
        Index('ix_fintrac_report_client_created', 'client_id', 'created_at'),
    )


class FintracAuditLog(Base):
    __tablename__ = "fintrac_audit_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("fintrac_reports.id"), nullable=False)
    
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # created, updated, submitted
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    details: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Relationships
    report: Mapped["FintracReport"] = relationship("FintracReport", back_populates="audit_logs")
    changer: Mapped["User"] = relationship("User")
```

```