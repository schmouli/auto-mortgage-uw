from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, ForeignKey, Numeric, Boolean, Text, CheckConstraint, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional, List

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sin_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # SHA256 hash for lookup
    sin_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AES-256 encrypted
    date_of_birth_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AES-256 encrypted
    employment_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    employer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    years_employed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    annual_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    other_income: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    credit_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    marital_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="client", uselist=False)
    applications: Mapped[List["MortgageApplication"]] = relationship("MortgageApplication", back_populates="client")


    __table_args__ = (
        CheckConstraint("annual_income >= 0", name="check_annual_income_non_negative"),
        Index('ix_clients_user_id', 'user_id'),
    )


class MortgageApplication(Base):
    __tablename__ = "mortgage_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    application_type: Mapped[str] = mapped_column(String(50), nullable=False)  # purchase, refinance, renewal, transfer
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)  # draft, submitted, under_review, approved, denied
    property_address: Mapped[str] = mapped_column(Text, nullable=False)
    property_type: Mapped[str] = mapped_column(String(100), nullable=False)  # single_family, condo, townhouse, multi_unit, rural
    property_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    down_payment: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    requested_loan_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    amortization_years: Mapped[int] = mapped_column(Integer, nullable=False)
    term_years: Mapped[int] = mapped_column(Integer, nullable=False)
    mortgage_type: Mapped[str] = mapped_column(String(50), nullable=False)  # fixed, variable
    ltv_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    gds_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    tds_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    insurance_required: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    insurance_premium_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="applications")
    broker: Mapped[Optional["User"]] = relationship("User", foreign_keys=[broker_id])
    co_borrowers: Mapped[List["CoBorrower"]] = relationship("CoBorrower", back_populates="application", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("property_value > 0", name="check_property_value_positive"),
        CheckConstraint("purchase_price > 0", name="check_purchase_price_positive"),
        CheckConstraint("down_payment >= 0", name="check_down_payment_non_negative"),
        CheckConstraint("requested_loan_amount >= 0", name="check_requested_loan_amount_non_negative"),
        CheckConstraint("amortization_years BETWEEN 5 AND 30", name="check_amortization_years_range"),
        CheckConstraint("term_years BETWEEN 1 AND 10", name="check_term_years_range"),
        Index('ix_mortgage_applications_client_id', 'client_id'),
        Index('ix_mortgage_applications_broker_id', 'broker_id'),
        Index('ix_mortgage_applications_status', 'status'),
    )


class CoBorrower(Base):
    __tablename__ = "co_borrowers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sin_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # SHA256 hash for lookup
    sin_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AES-256 encrypted
    annual_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    employment_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    credit_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="co_borrowers")

    __table_args__ = (
        CheckConstraint("annual_income >= 0", name="check_co_borrower_income_non_negative"),
        Index('ix_co_borrowers_application_id', 'application_id'),
    )