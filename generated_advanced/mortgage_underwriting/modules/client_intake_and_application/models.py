from datetime import datetime
from decimal import Decimal
from sqlalchemy import Index, Numeric, String, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base

class Client(Base):
    """Client profile with encrypted PII for PIPEDA compliance."""

    __tablename__ = "clients"
    __table_args__ = (
        CheckConstraint("annual_income >= 0", name="check_annual_income_non_negative"),
        CheckConstraint("other_income >= 0", name="check_other_income_non_negative"),
        CheckConstraint("credit_score >= 0 AND credit_score <= 900", name="check_credit_score_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    sin_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # AES-256 encrypted
    date_of_birth: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD (encrypted)
    employment_status: Mapped[str] = mapped_column(String(50), nullable=False)
    employer_name: Mapped[Optional[str]] = mapped_column(String(255))
    years_employed: Mapped[int] = mapped_column(default=0)
    annual_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)  # CAD
    other_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal('0.00'))
    credit_score: Mapped[int] = mapped_column(nullable=False)
    marital_status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="client")  # From auth module
    applications: Mapped[List["MortgageApplication"]] = relationship("MortgageApplication", back_populates="client", cascade="all, delete-orphan")


class MortgageApplication(Base):
    """Main mortgage application form with audit trail."""

    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint("property_value >= 0", name="check_property_value_non_negative"),
        CheckConstraint("purchase_price >= 0", name="check_purchase_price_non_negative"),
        CheckConstraint("down_payment >= 0", name="check_down_payment_non_negative"),
        CheckConstraint("requested_loan_amount >= 0", name="check_requested_loan_amount_non_negative"),
        CheckConstraint("amortization_years >= 5 AND amortization_years <= 30", name="check_amortization_years_range"),
        CheckConstraint("term_years >= 1 AND term_years <= 10", name="check_term_years_range"),
        Index('ix_applications_client_status', 'client_id', 'status'),
        Index('ix_applications_broker_status', 'broker_id', 'status'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    application_type: Mapped[str] = mapped_column(String(20), nullable=False)  # purchase/refinance/renewal
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    property_address: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted
    property_type: Mapped[str] = mapped_column(String(20), nullable=False)  # single_family/condo/townhouse/duplex
    property_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))  # Required for refinance
    purchase_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))  # Required for purchase
    down_payment: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    requested_loan_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    amortization_years: Mapped[int] = mapped_column(nullable=False)
    term_years: Mapped[int] = mapped_column(nullable=False)
    mortgage_type: Mapped[str] = mapped_column(String(20), nullable=False)  # fixed/variable
    ltv_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    insurance_required: Mapped[bool] = mapped_column(default=False)
    cmhc_premium_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="applications")
    co_borrowers: Mapped[List["CoBorrower"]] = relationship("CoBorrower", back_populates="application", cascade="all, delete-orphan")


class CoBorrower(Base):
    """Co-borrower information with encrypted SIN."""

    __tablename__ = "co_borrowers"
    __table_args__ = (
        CheckConstraint("annual_income >= 0", name="check_co_borrower_annual_income_non_negative"),
        CheckConstraint("credit_score >= 0 AND credit_score <= 900", name="check_co_borrower_credit_score_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sin_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # AES-256 encrypted
    annual_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    employment_status: Mapped[str] = mapped_column(String(50), nullable=False)
    credit_score: Mapped[int] = mapped_column(nullable=False)

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="co_borrowers")