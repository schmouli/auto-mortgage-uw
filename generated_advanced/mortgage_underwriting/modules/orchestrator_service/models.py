from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import (
    String, Numeric, DateTime, ForeignKey, JSON, Index, Integer, Text,
    UniqueConstraint, CheckConstraint, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class ApplicationStatus(str, Enum):
    SUBMITTED = "submitted"
    EXTRACTING = "extracting"
    EVALUATING = "evaluating"
    DECIDED = "decided"
    EXCEPTION = "exception"


class EmploymentType(str, Enum):
    SALARIED = "salaried"
    SELF_EMPLOYED = "self_employed"
    CONTRACT = "contract"


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index('ix_applications_borrower_id', 'borrower_id'),
        Index('ix_applications_status', 'status'),
        Index('ix_applications_created_at', 'created_at'),
        CheckConstraint('purchase_price > 0', name='check_purchase_price_positive'),
        CheckConstraint('mortgage_amount > 0', name='check_mortgage_amount_positive'),
        CheckConstraint('property_value > 0', name='check_property_value_positive'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, index=True)
    borrower_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    lender_id: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(String(20), default=ApplicationStatus.SUBMITTED, nullable=False)
    property_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    mortgage_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    contract_interest_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    borrower: Mapped["Borrower"] = relationship("Borrower", back_populates="applications", lazy="selectin")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="application", lazy="selectin")
    fintrac_reports: Mapped[List["FINTRACReport"]] = relationship("FINTRACReport", back_populates="application", lazy="selectin")

    def __repr__(self) -> str:
        return f'<Application(id={self.id}, borrower_id="{self.borrower_id}", status="{self.status}")>'


class Borrower(Base):
    __tablename__ = "borrowers"
    __table_args__ = (
        Index('ix_borrowers_sin_hash', 'sin_hash'),
        Index('ix_borrowers_credit_score', 'credit_score'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sin_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # SHA256 hash
    sin_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # AES-256 encrypted
    dob_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # AES-256 encrypted
    employment_type: Mapped[EmploymentType] = mapped_column(String(20), nullable=False)
    gross_annual_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    monthly_liability_payments: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal('0.00'))
    credit_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="borrower", lazy="selectin")

    def __repr__(self) -> str:
        return f'<Borrower(id={self.id}, full_name="{self.full_name}")>'


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index('ix_documents_application_id', 'application_id'),
        Index('ix_documents_document_type', 'document_type'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, index=True)
    application_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="documents")

    def __repr__(self) -> str:
        return f'<Document(id={self.id}, type="{self.document_type}", app_id="{self.application_id}")>'


class FINTRACReport(Base):
    __tablename__ = "fintrac_reports"
    __table_args__ = (
        Index('ix_fintrac_reports_application_id', 'application_id'),
        Index('ix_fintrac_reports_client_id', 'client_id'),
        Index('ix_fintrac_reports_transaction_type', 'transaction_type'),
        Index('ix_fintrac_reports_created_at', 'created_at'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, index=True)
    application_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    client_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "large_cash", "wire_transfer"
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CAD", nullable=False)
    is_high_risk: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, verified, rejected
    report_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="fintrac_reports")

    def __repr__(self) -> str:
        return f'<FINTRACReport(id={self.id}, type="{self.transaction_type}", amount={self.amount})>'