from datetime import datetime
from decimal import Decimal
from sqlalchemy import Index, Numeric, String, DateTime, Text, ForeignKey, Boolean, Date, CheckConstraint
time
from typing import Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base

class FintracVerification(Base):
    __tablename__ = "fintrac_verifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    verification_method: Mapped[str] = mapped_column(String(20), nullable=False)  # in_person, credit_file, dual_process
    id_type: Mapped[str] = mapped_column(String(50), nullable=False)
    id_number_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    id_expiry_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    id_issuing_province: Mapped[str] = mapped_column(String(2), nullable=False)
    verified_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_pep: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), default="low", nullable=False)  # low, medium, high
    record_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retention_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # FIXED: Added 5-year retention tracking
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)  # FIXED: Immutable audit trail

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="fintrac_verifications")
    client: Mapped["Client"] = relationship("Client", back_populates="fintrac_verifications")

    __table_args__ = (
        Index('ix_fintrac_verifications_application_id', 'application_id'),
        Index('ix_fintrac_verifications_client_id', 'client_id'),
        CheckConstraint("risk_level IN ('low', 'medium', 'high')", name="check_risk_level"),
        CheckConstraint("verification_method IN ('in_person', 'credit_file', 'dual_process')", name="check_verification_method"),
    )


class FintracReport(Base):
    __tablename__ = "fintrac_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)  # large_cash_transaction, suspicious_transaction, terrorist_property
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CAD", nullable=False)
    report_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    submitted_to_fintrac_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fintrac_reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_large_transaction_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # FIXED: Explicit flag for >$10,000
    retention_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # FIXED: Added 5-year retention tracking

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="fintrac_reports")

    __table_args__ = (
        Index('ix_fintrac_reports_application_id', 'application_id'),
        CheckConstraint("report_type IN ('large_cash_transaction', 'suspicious_transaction', 'terrorist_property')", name="check_report_type"),
    )