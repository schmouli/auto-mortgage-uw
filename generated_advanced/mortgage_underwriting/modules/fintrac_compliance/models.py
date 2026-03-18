from datetime import datetime
from decimal import Decimal
from sqlalchemy import Index, Numeric, String, Boolean, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base

class FintracVerification(Base):
    """FINTRAC identity verification record with immutable audit trail.
    
    Complies with FINTRAC PCMLTFA requirements for client identification,
    risk assessment, and enhanced due diligence triggers.
    """
    __tablename__ = "fintrac_verifications"
    __table_args__ = (
        CheckConstraint("risk_level IN ('low', 'medium', 'high')", name="check_risk_level"),
        CheckConstraint("verification_method IN ('in_person', 'credit_file', 'dual_process')", name="check_verification_method"),
        CheckConstraint("id_type IN ('passport', 'drivers_license', 'provincial_id', 'certificate_of_citizenship')", name="check_id_type"),
        Index("ix_fintrac_verifications_application_id", "application_id"),
        Index("ix_fintrac_verifications_client_id", "client_id"),
        Index("ix_fintrac_verifications_verified_at", "verified_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    verification_method: Mapped[str] = mapped_column(String(20), nullable=False)
    id_type: Mapped[str] = mapped_column(String(30), nullable=False)
    id_number_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted via common/security.py
    id_expiry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_issuing_province: Mapped[str] = mapped_column(String(2), nullable=False)
    verified_by: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_pep: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Politically Exposed Person
    is_hio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # High Integrity Origin
    risk_level: Mapped[str] = mapped_column(String(10), default="low", nullable=False)
    source_of_funds: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occupation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    employer: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Soft delete only
    record_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="fintrac_verifications", lazy="selectin")
    client: Mapped["Client"] = relationship("Client", back_populates="fintrac_verifications", lazy="selectin")
    verifier: Mapped["User"] = relationship("User", back_populates="fintrac_verifications", lazy="selectin")


class FintracReport(Base):
    """FINTRAC transaction reporting records with 5-year retention.
    
    Covers large cash transactions, suspicious activity, and terrorist property reports.
    """
    __tablename__ = "fintrac_reports"
    __table_args__ = (
        CheckConstraint("report_type IN ('large_cash_transaction', 'suspicious_transaction', 'terrorist_property')", name="check_report_type"),
        CheckConstraint("currency IN ('CAD', 'USD', 'EUR', 'GBP')", name="check_currency"),
        Index("ix_fintrac_reports_application_id", "application_id"),
        Index("ix_fintrac_reports_report_date", "report_date"),
        Index("ix_fintrac_reports_submitted_to_fintrac_at", "submitted_to_fintrac_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)  # Financial values always Decimal
    currency: Mapped[str] = mapped_column(String(3), default="CAD", nullable=False)
    report_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_to_fintrac_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fintrac_reference_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_by: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Soft delete only - records never truly deleted per FINTRAC
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="fintrac_reports", lazy="selectin")
    reporter: Mapped["User"] = relationship("User", back_populates="fintrac_reports", lazy="selectin")