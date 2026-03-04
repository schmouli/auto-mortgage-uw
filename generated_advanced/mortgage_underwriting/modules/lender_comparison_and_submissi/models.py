```python
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Text,
    Numeric,
    Date,
    UniqueConstraint
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from pydantic import BaseModel as PydanticBaseModel
from enum import Enum as PyEnum

# Assuming Base class is defined elsewhere in the project
from database.base import Base


class LenderType(str, PyEnum):
    BANK = "bank"
    CREDIT_UNION = "credit_union"
    MONOLINE = "monoline"
    PRIVATE = "private"
    MFC = "mfc"


class MortgageType(str, PyEnum):
    FIXED = "fixed"
    VARIABLE = "variable"
    HELOC = "heloc"


class RateType(str, PyEnum):
    POSTED = "posted"
    DISCOUNTED = "discounted"
    PRIME_PLUS = "prime_plus"


class SubmissionStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    COUNTERED = "countered"


class BaseModel(PydanticBaseModel):
    class Config:
        arbitrary_types_allowed = True


class Lender(Base):
    __tablename__ = 'lenders'
    __table_args__ = (
        CheckConstraint("type IN ('bank', 'credit_union', 'monoline', 'private', 'mfc')", name='check_lender_type'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[LenderType] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    submission_email: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    products: Mapped[List["LenderProduct"]] = relationship("LenderProduct", back_populates="lender")
    submissions: Mapped[List["LenderSubmission"]] = relationship("LenderSubmission", back_populates="lender")


class LenderProduct(Base):
    __tablename__ = 'lender_products'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lender_id: Mapped[int] = mapped_column(ForeignKey('lenders.id'), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mortgage_type: Mapped[MortgageType] = mapped_column(String(20), nullable=False)
    term_years: Mapped[Optional[int]] = mapped_column(Integer)  # NULL for HELOCs
    rate: Mapped[Decimal] = mapped_column(Numeric(precision=6, scale=4), nullable=False)
    rate_type: Mapped[RateType] = mapped_column(String(20), nullable=False)
    max_ltv_insured: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=2), nullable=False)
    max_ltv_conventional: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=2), nullable=False)
    max_amortization_insured: Mapped[int] = mapped_column(Integer, nullable=False)
    max_amortization_conventional: Mapped[int] = mapped_column(Integer, nullable=False)
    min_credit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    max_gds: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=2), nullable=False)
    max_tds: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=2), nullable=False)
    allows_self_employed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allows_rental_income: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allows_gifted_down_payment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prepayment_privilege_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=5, scale=2))
    portability: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assumability: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    lender: Mapped["Lender"] = relationship("Lender", back_populates="products")
    submissions: Mapped[List["LenderSubmission"]] = relationship("LenderSubmission", back_populates="product")

    __table_args__ = (
        CheckConstraint("mortgage_type IN ('fixed', 'variable', 'heloc')", name='check_mortgage_type'),
        CheckConstraint("rate_type IN ('posted', 'discounted', 'prime_plus')", name='check_rate_type'),
        CheckConstraint("max_ltv_insured >= 0 AND max_ltv_insured <= 95", name='check_max_ltv_insured_range'),
        CheckConstraint("max_ltv_conventional >= 0 AND max_ltv_conventional <= 80", name='check_max_ltv_conventional_range'),
        CheckConstraint("min_credit_score >= 300 AND min_credit_score <= 900", name='check_min_credit_score_range'),
        CheckConstraint("max_gds >= 0 AND max_gds <= 100", name='check_max_gds_range'),
        CheckConstraint("max_tds >= 0 AND max_tds <= 100", name='check_max_tds_range'),
        UniqueConstraint('lender_id', 'product_name', name='uq_lender_product_name')
    )


class LenderSubmission(Base):
    __tablename__ = 'lender_submissions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey('applications.id'), nullable=False)
    lender_id: Mapped[int] = mapped_column(ForeignKey('lenders.id'), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey('lender_products.id'), nullable=False)
    submitted_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[SubmissionStatus] = mapped_column(String(20), default=SubmissionStatus.PENDING, nullable=False)
    lender_reference_number: Mapped[Optional[str]] = mapped_column(String(100))
    lender_conditions: Mapped[Optional[str]] = mapped_column(Text)
    approved_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=6, scale=4))
    approved_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=15, scale=2))
    expiry_date: Mapped[Optional[Date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    lender: Mapped["Lender"] = relationship("Lender", back_populates="submissions")
    product: Mapped["LenderProduct"] = relationship("LenderProduct", back_populates="submissions")

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'declined', 'countered')", name='check_submission_status'),
    )
```