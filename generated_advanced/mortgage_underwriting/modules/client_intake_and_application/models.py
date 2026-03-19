from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, ForeignKey, Numeric, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional, List

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    sin_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    date_of_birth_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # FIXED: Added encrypted storage for DOB
    employment_status: Mapped[str] = mapped_column(String(50), nullable=False)
    employer_name: Mapped[Optional[str]] = mapped_column(String(255))
    years_employed: Mapped[Optional[int]] = mapped_column(Integer)
    annual_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    other_income: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    credit_score: Mapped[Optional[int]] = mapped_column(Integer)
    marital_status: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="client")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="client", cascade="all, delete-orphan")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    application_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    property_address: Mapped[dict] = mapped_column(JSONB, nullable=False)
    property_type: Mapped[str] = mapped_column(String(50), nullable=False)
    property_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    purchase_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    down_payment: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    requested_loan_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    amortization_years: Mapped[int] = mapped_column(Integer, nullable=False)
    term_years: Mapped[int] = mapped_column(Integer, nullable=False)
    mortgage_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="applications")
    broker: Mapped[Optional["User"]] = relationship("User", foreign_keys=[broker_id])
    co_borrowers: Mapped[List["CoBorrower"]] = relationship("CoBorrower", back_populates="application", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("amortization_years BETWEEN 5 AND 30", name="check_amortization_range"),
        CheckConstraint("term_years BETWEEN 1 AND 10", name="check_term_range"),
        CheckConstraint("property_value > 0", name="check_property_value_positive"),
        CheckConstraint("requested_loan_amount > 0", name="check_requested_loan_positive"),
    )


class CoBorrower(Base):
    __tablename__ = "co_borrowers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sin_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    date_of_birth_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # FIXED: Added encrypted storage for DOB
    annual_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    employment_status: Mapped[str] = mapped_column(String(50), nullable=False)
    credit_score: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="co_borrowers")