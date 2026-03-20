from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"
    __table_args__ = (
        Index('ix_extraction_jobs_application_id_status', 'application_id', 'status'),
        Index('ix_extraction_jobs_created_at', 'created_at'),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    priority: Mapped[int] = mapped_column(default=5)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    extracted_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="extractions")