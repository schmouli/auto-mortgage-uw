from datetime import datetime
from decimal import Decimal
from sqlalchemy import Index, Numeric, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sin_encrypted: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[str] = mapped_column(String(255), nullable=False)  # Encrypted
    employment_status: Mapped[str] = mapped_column(String(100), nullable=False)
    employer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    years_employed: Mapped[int] = mapped_column(default=0, nullable=False)
    annual_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    other_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0, nullable=False)
    credit_score: Mapped[int] = mapped_column(nullable=False)
    marital_status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    applications: Mapped[List["MortgageApplication"]] = relationship("MortgageApplication", back_populates="client", cascade="all, delete-orphan")
    co_borrowers: Mapped[List["CoBorrower"]] = relationship("CoBorrower", back_populates="client", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_clients_user_id', 'user_id'),
    )


class MortgageApplication(Base):
    __tablename__ = "mortgage_applications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    application_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    property_address: Mapped[str] = mapped_column(Text, nullable=False)
    property_type: Mapped[str] = mapped_column(String(100), nullable=False)
    property_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    down_payment: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    requested_loan_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    amortization_years: Mapped[int] = mapped_column(nullable=False)
    term_years: Mapped[int] = mapped_column(nullable=False)
    mortgage_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="applications")
    co_borrowers: Mapped[List["CoBorrower"]] = relationship("CoBorrower", back_populates="application", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_mortgage_applications_client_id', 'client_id'),
        Index('ix_mortgage_applications_broker_id', 'broker_id'),
        Index('ix_mortgage_applications_status', 'status'),
    )


class CoBorrower(Base):
    __tablename__ = "co_borrowers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sin_encrypted: Mapped[str] = mapped_column(String(255), nullable=False)
    annual_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    employment_status: Mapped[str] = mapped_column(String(100), nullable=False)
    credit_score: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="co_borrowers")
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="co_borrowers")

    __table_args__ = (
        Index('ix_co_borrowers_client_id', 'client_id'),
        Index('ix_co_borrowers_application_id', 'application_id'),
    )