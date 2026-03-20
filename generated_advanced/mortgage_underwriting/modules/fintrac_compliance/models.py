from datetime import datetime
from decimal import Decimal
from sqlalchemy import Index, Numeric, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from mortgage_underwriting.common.database import Base


class FintracVerification(Base):
    """FINTRAC identity verification record with immutable audit trail."""

    __tablename__ = "fintrac_verifications"
    __table_args__ = (
        Index('ix_fintrac_verifications_client_id', 'client_id'),
        Index('ix_fintrac_verifications_application_id', 'application_id'),
        Index('ix_fintrac_verifications_verified_at', 'verified_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    verification_method: Mapped[str] = mapped_column(String(20), nullable=False)  # in_person, credit_file, dual_process
    id_type: Mapped[str] = mapped_column(String(50), nullable=False)
    id_number_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # AES-256 encrypted
    id_expiry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_issuing_province: Mapped[str] = mapped_column(String(2), nullable=False)
    verified_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_pep: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Politically Exposed Person
    is_hio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # High Integrity Origin
    risk_level: Mapped[str] = mapped_column(String(10), default="low", nullable=False)  # low, medium, high
    record_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    retention_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # 5-year retention from creation

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="fintrac_verifications")
    client: Mapped["Client"] = relationship("Client", back_populates="fintrac_verifications")


class FintracReport(Base):
    """FINTRAC transaction reporting with immutable audit trail."""

    __tablename__ = "fintrac_reports"
    __table_args__ = (
        Index('ix_fintrac_reports_application_id', 'application_id'),
        Index('ix_fintrac_reports_report_date', 'report_date'),
        Index('ix_fintrac_reports_created_by', 'created_by'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)  # large_cash_transaction, suspicious_transaction, terrorist_property
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CAD", nullable=False)
    report_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_to_fintrac_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fintrac_reference_number: Mapped[Optional[str]] = mapped_column(String(100))
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    retention_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # 5-year retention from creation
    requires_high_value_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Flag for transactions > $10,000

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="fintrac_reports")