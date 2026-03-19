from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy import Integer, String, DateTime, ForeignKey, Numeric, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class DocumentTypeEnum(str, PyEnum):
    T4506 = "t4506"
    NOA = "noa"
    CREDIT = "credit"
    BANK = "bank"
    PURCHASE = "purchase"


class ExtractionStatusEnum(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Extraction(Base):
    __tablename__ = "extractions"
    __table_args__ = (
        Index('ix_extractions_application_id', 'application_id'),
        Index('ix_extractions_status', 'status'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("mortgage_applications.id", ondelete="CASCADE"), nullable=False)
    document_type: Mapped[DocumentTypeEnum] = mapped_column(String(20), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[ExtractionStatusEnum] = mapped_column(String(20), default=ExtractionStatusEnum.PENDING, nullable=False)
    estimated_processing_time_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    application: Mapped["MortgageApplication"] = relationship("MortgageApplication", back_populates="extractions")