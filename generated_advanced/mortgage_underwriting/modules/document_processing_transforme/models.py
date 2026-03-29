from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from sqlalchemy import Index, Numeric, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class DocumentType(str, PyEnum):
    T4 = "t4"
    NOA = "noa"
    CREDIT_REPORT = "credit_report"
    BANK_STATEMENT = "bank_statement"
    PURCHASE_AGREEMENT = "purchase_agreement"


class JobStatus(str, PyEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"
    __table_args__ = (
        Index("ix_extraction_jobs_application_id", "application_id"),
        Index("ix_extraction_jobs_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(String(50), nullable=False)
    s3_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    callback_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    status: Mapped[JobStatus] = mapped_column(String(20), default=JobStatus.QUEUED, nullable=False)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    extracted_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="extractions")