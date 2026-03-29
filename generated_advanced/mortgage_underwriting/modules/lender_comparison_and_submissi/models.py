from datetime import datetime
from decimal import Decimal
from sqlalchemy import Index, Numeric, String, DateTime, Text, ForeignKey, Boolean, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class Lender(Base):
    __tablename__ = "lenders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # bank/credit_union/monoline/private/mfc
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    submission_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    products: Mapped[List["LenderProduct"]] = relationship("LenderProduct", back_populates="lender", cascade="all, delete-orphan")
    submissions: Mapped[List["LenderSubmission"]] = relationship("LenderSubmission", back_populates="lender")

    __table_args__ = (
        CheckConstraint("type IN ('bank', 'credit_union', 'monoline', 'private', 'mfc')", name='check_lender_type'),
    )


class LenderProduct(Base):
    __tablename__ = "lender_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lender_id: Mapped[int] = mapped_column(ForeignKey("lenders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mortgage_type: Mapped[str] = mapped_column(String(20), nullable=False)  # fixed/variable/heloc
    term_years: Mapped[Decimal] = mapped_column(Numeric(3, 1), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    rate_type: Mapped[str] = mapped_column(String(20), nullable=False)  # posted/discounted/prime_plus
    max_ltv_insured: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_ltv_conventional: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_amortization_insured: Mapped[int] = mapped_column(Integer, nullable=False)
    max_amortization_conventional: Mapped[int] = mapped_column(Integer, nullable=False)
    min_credit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    max_gds: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_tds: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    allows_self_employed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allows_rental_income: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allows_gifted_down_payment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prepayment_privilege_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    portability: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assumability: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    lender: Mapped["Lender"] = relationship("Lender", back_populates="products")
    submissions: Mapped[List["LenderSubmission"]] = relationship("LenderSubmission", back_populates="product")

    __table_args__ = (
        Index('ix_lender_products_lender_id', 'lender_id'),
        Index('ix_lender_products_is_active', 'is_active'),
        CheckConstraint("mortgage_type IN ('fixed', 'variable', 'heloc')", name='check_mortgage_type'),
        CheckConstraint("rate_type IN ('posted', 'discounted', 'prime_plus')", name='check_rate_type'),
        CheckConstraint("max_ltv_insured >= 0 AND max_ltv_insured <= 100", name='check_max_ltv_insured'),
        CheckConstraint("max_ltv_conventional >= 0 AND max_ltv_conventional <= 100", name='check_max_ltv_conventional'),
        CheckConstraint("min_credit_score >= 300 AND min_credit_score <= 900", name='check_min_credit_score'),
        CheckConstraint("max_gds >= 0 AND max_gds <= 100", name='check_max_gds'),
        CheckConstraint("max_tds >= 0 AND max_tds <= 100", name='check_max_tds'),
        CheckConstraint("prepayment_privilege_percent >= 0 AND prepayment_privilege_percent <= 100", name='check_prepayment_privilege'),
    )


class LenderSubmission(Base):
    __tablename__ = "lender_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    lender_id: Mapped[int] = mapped_column(ForeignKey("lenders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("lender_products.id", ondelete="SET NULL"), nullable=True)
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending/approved/declined/countered
    lender_reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lender_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 3), nullable=True)
    approved_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="submissions")
    lender: Mapped["Lender"] = relationship("Lender", back_populates="submissions")
    product: Mapped[Optional["LenderProduct"]] = relationship("LenderProduct", back_populates="submissions")
    submitter: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        Index('ix_lender_submissions_application_id', 'application_id'),
        Index('ix_lender_submissions_lender_id', 'lender_id'),
        Index('ix_lender_submissions_status', 'status'),
        CheckConstraint("status IN ('pending', 'approved', 'declined', 'countered')", name='check_submission_status'),
    )