from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import (
    Index,
    Numeric,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class ApplicationStatus(str, PyEnum):
    SUBMITTED = "submitted"
    EXTRACTING = "extracting"
    EVALUATING = "evaluating"
    DECIDED = "decided"
    EXCEPTION = "exception"


class EmploymentType(str, PyEnum):
    SALARIED = "salaried"
    SELF_EMPLOYED = "self-employed"
    CONTRACT = "contract"


class Borrower(Base):
    __tablename__ = "borrowers"
    __table_args__ = (
        Index("ix_borrowers_sin_hash", "sin_hash"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sin_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    employment_type: Mapped[EmploymentType] = mapped_column(String(20), nullable=False)
    gross_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    credit_score: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    applications: Mapped[List["MortgageApplication"]] = relationship(
        "MortgageApplication",
        back_populates="borrower",
        lazy="selectin",
    )


class MortgageApplication(Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index("ix_applications_borrower_id", "borrower_id"),
        Index("ix_applications_lender_id", "lender_id"),
        Index("ix_applications_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    borrower_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("borrowers.id", ondelete="CASCADE"),
        nullable=False,
    )
    lender_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(String(20), default=ApplicationStatus.SUBMITTED, nullable=False)
    property_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    mortgage_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    ltv_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    insurance_required: Mapped[bool] = mapped_column(Boolean, default=False)
    insurance_premium: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4), nullable=True)
    decision_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    borrower: Mapped["Borrower"] = relationship("Borrower", back_populates="applications", lazy="selectin")