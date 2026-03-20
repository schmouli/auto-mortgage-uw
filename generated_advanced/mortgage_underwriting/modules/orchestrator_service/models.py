from datetime import datetime
from decimal import Decimal
from enum import Enum
from sqlalchemy import Integer, String, DateTime, Numeric, Boolean, Text, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class ApplicationStatus(str, Enum):
    submitted = "submitted"
    extracting = "extracting"
    evaluating = "evaluating"
    decided = "decided"
    exception = "exception"


class EmploymentType(str, Enum):
    salaried = "salaried"
    self_employed = "self_employed"
    contract = "contract"


class DocumentType(str, Enum):
    paystub = "paystub"
    t4 = "t4"
    notice_of_assessment = "notice_of_assessment"
    bank_statement = "bank_statement"
    property_appraisal = "property_appraisal"


class Application(Base):
    __tablename__ = "applications"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    borrower_id: Mapped[int] = mapped_column(Integer, ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False, index=True)
    lender_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[ApplicationStatus] = mapped_column(ENUM(ApplicationStatus, name="application_status_enum"), default=ApplicationStatus.submitted, nullable=False)
    property_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    mortgage_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    borrower: Mapped["Borrower"] = relationship("Borrower", back_populates="applications")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="application", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_applications_borrower_id_status', 'borrower_id', 'status'),
        Index('ix_applications_lender_id', 'lender_id'),
        CheckConstraint('property_value >= 0', name='check_property_value_positive'),
        CheckConstraint('purchase_price >= 0', name='check_purchase_price_positive'),
        CheckConstraint('mortgage_amount >= 0', name='check_mortgage_amount_positive'),
    )


class Borrower(Base):
    __tablename__ = "borrowers"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sin_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)  # SHA256 hash
    sin_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # AES-256 encrypted
    date_of_birth_encrypted: Mapped[str] = mapped_column(Text, nullable=False)  # AES-256 encrypted
    employment_type: Mapped[EmploymentType] = mapped_column(ENUM(EmploymentType, name="employment_type_enum"), nullable=False)
    gross_income: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    credit_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="borrower")
    
    __table_args__ = (
        Index('ix_borrowers_sin_hash', 'sin_hash'),
        CheckConstraint('gross_income >= 0', name='check_gross_income_positive'),
        CheckConstraint('credit_score IS NULL OR (credit_score >= 300 AND credit_score <= 900)', name='check_credit_score_range'),
    )


class Document(Base):
    __tablename__ = "documents"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type: Mapped[DocumentType] = mapped_column(ENUM(DocumentType, name="document_type_enum"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="documents")
    
    __table_args__ = (
        Index('ix_documents_application_id', 'application_id'),
    )


class FintracVerification(Base):
    __tablename__ = "fintrac_verifications"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    transaction_reported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    application: Mapped["Application"] = relationship("Application")