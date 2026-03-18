from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional
import enum

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class DocumentType(str, enum.Enum):
    GOVERNMENT_ID = "government_id"
    PROOF_OF_SIN = "proof_of_sin"
    T4_SLIP = "t4_slip"
    NOA = "noa"
    PAY_STUB = "pay_stub"
    EMPLOYMENT_LETTER = "employment_letter"
    T1_GENERAL = "t1_general"
    FINANCIAL_STATEMENTS = "financial_statements"
    RENTAL_INCOME_STATEMENT = "rental_income_statement"
    PURCHASE_AGREEMENT = "purchase_agreement"
    MLS_LISTING = "mls_listing"
    PROPERTY_TAX_BILL = "property_tax_bill"
    CONDO_STATUS_CERT = "condo_status_cert"
    BANK_STATEMENT = "bank_statement"
    VOID_CHEQUE = "void_cheque"
    GIFT_LETTER = "gift_letter"
    RRSP_WITHDRAWAL_CONFIRMATION = "rrsp_withdrawal_confirmation"
    SALE_PROCEEDS_CONFIRMATION = "sale_proceeds_confirmation"
    EXISTING_MORTGAGE_STATEMENT = "existing_mortgage_statement"
    DIVORCE_DECREE = "divorce_decree"
    BANKRUPTCY_DISCHARGE = "bankruptcy_discharge"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class DocumentCategory(str, enum.Enum):
    IDENTITY = "IDENTITY"
    INCOME = "INCOME"
    PROPERTY = "PROPERTY"
    BANKING = "BANKING"
    DOWN_PAYMENT = "DOWN_PAYMENT"
    OTHER = "OTHER"


class DocumentRequirementCategory(str, enum.Enum):
    IDENTITY = "IDENTITY"
    INCOME = "INCOME"
    PROPERTY = "PROPERTY"
    BANKING = "BANKING"
    DOWN_PAYMENT = "DOWN_PAYMENT"
    OTHER = "OTHER"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    document_type: Mapped[DocumentType] = mapped_column(SQLEnum(DocumentType), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(SQLEnum(DocumentStatus), default=DocumentStatus.PENDING)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="documents")
    uploader: Mapped["User"] = relationship("User", foreign_keys=[uploaded_by])
    verifier: Mapped["User"] = relationship("User", foreign_keys=[verified_by])


class DocumentRequirement(Base):
    __tablename__ = "document_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type: Mapped[DocumentType] = mapped_column(SQLEnum(DocumentType), nullable=False)
    category: Mapped[DocumentRequirementCategory] = mapped_column(SQLEnum(DocumentRequirementCategory), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    is_received: Mapped[bool] = mapped_column(Boolean, default=False)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="requirements")