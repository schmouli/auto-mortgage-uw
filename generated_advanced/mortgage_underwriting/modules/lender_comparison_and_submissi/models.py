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
    UniqueConstraint,
    Index
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from pydantic import BaseModel as PydanticBaseModel
from enum import Enum as PyEnum

# Assuming Base class is defined elsewhere in the project
from mortgage_underwriting.common.database import Base


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
    __table_args__ = (
        UniqueConstraint('lender_id', 'product_name', name='uq_lender_product_name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lender_id: Mapped[int] = mapped_column(Integer, ForeignKey('lenders.id'), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mortgage_type: Mapped[MortgageType] = mapped_column(String(50), nullable=False)
    term_years: Mapped[Optional[int]] = mapped_column(Integer)
    rate: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)  # FIXED: Changed from Float to Numeric(19, 4)
    rate_type: Mapped[RateType] = mapped_column(String(50), nullable=False)
    max_ltv_insured: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_ltv_conventional: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    min_credit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    min_down_payment: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    lender: Mapped["Lender"] = relationship("Lender", back_populates="products")
    lender_rates: Mapped[List["LenderRate"]] = relationship("LenderRate", back_populates="lender_product")


class LenderRate(Base):
    __tablename__ = 'lender_rates'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lender_product_id: Mapped[int] = mapped_column(Integer, ForeignKey('lender_products.id'), nullable=False)
    prime_rate: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)  # FIXED: Changed from Float to Numeric(19, 4)
    posted_rate: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)  # FIXED: Changed from Float to Numeric(19, 4)
    discount_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    effective_rate: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    valid_from: Mapped[Date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[Optional[Date]] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # FIXED: Added missing updated_at field

    # Relationships
    lender_product: Mapped["LenderProduct"] = relationship("LenderProduct", back_populates="lender_rates")
    lender_submissions: Mapped[List["LenderSubmission"]] = relationship("LenderSubmission", back_populates="lender_rate")  # FIXED: Added back_populates


class LenderSubmission(Base):
    __tablename__ = 'lender_submissions'
    __table_args__ = (
        Index('ix_lender_submission_lender_created', 'lender_id', 'created_at'),  # FIXED: Added composite index
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lender_id: Mapped[int] = mapped_column(Integer, ForeignKey('lenders.id'), nullable=False)
    lender_rate_id: Mapped[int] = mapped_column(Integer, ForeignKey('lender_rates.id'), nullable=False)
    application_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_number: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(String(50), default=SubmissionStatus.PENDING, nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    package_data: Mapped[Optional[str]] = mapped_column(Text)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    lender: Mapped["Lender"] = relationship("Lender", back_populates="submissions")
    lender_rate: Mapped["LenderRate"] = relationship("LenderRate", back_populates="lender_submissions")  # FIXED: Added back_populates
```

```