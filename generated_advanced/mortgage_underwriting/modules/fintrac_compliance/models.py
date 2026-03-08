from datetime import datetime
from decimal import Decimal
from sqlalchemy import Index, Numeric, String, Boolean, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class FintracVerification(Base):
    __tablename__ = "fintrac_verifications"
    __table_args__ = (
        Index('ix_fintrac_verifications_application_client', 'application_id', 'client_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    verification_method: Mapped[str] = mapped_column(String(20), nullable=False)  # in_person, credit_file, dual_process
    id_type: Mapped[str] = mapped_column(String(20), nullable=False)  # drivers_license, passport, provincial_id, other
    id_number_encrypted: Mapped[str] = mapped_column(String(255), nullable=False)
    id_expiry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_issuing_province: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    verified_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_pep: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_hio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), default="low", nullable=False)  # low, medium, high
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    # REMOVED deleted_at to ensure immutable audit trail per FINTRAC requirements

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="fintrac_verifications", lazy="selectin")
    client: Mapped["Client"] = relationship("Client", back_populates="fintrac_verifications", lazy="selectin")


class FintracReport(Base):
    __tablename__ = "fintrac_reports"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="check_amount_non_negative"),
        Index('ix_fintrac_reports_application', 'application_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)  # large_cash_transaction, suspicious_transaction, terrorist_property
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CAD", nullable=False)
    report_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_to_fintrac_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fintrac_reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    # REMOVED deleted_at to ensure immutable audit trail per FINTRAC requirements

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="fintrac_reports", lazy="selectin")