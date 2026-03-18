from datetime import datetime
from decimal import Decimal
from sqlalchemy import Index, Numeric, String, DateTime, ForeignKey, Text, UUID as SQLUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from uuid import UUID

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class Extraction(Base):
    """PDF document extraction job and results.
    
    Tracks all submitted documents through the Donut processing pipeline.
    Stores structured JSON output and confidence scores for audit/compliance.
    """

    __tablename__ = "extractions"
    __table_args__ = (
        Index("ix_extractions_application_id", "application_id"),
        Index("ix_extractions_status", "status"),
        Index("ix_extractions_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=func.gen_random_uuid())
    application_id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)  # t4, noa, credit, bank, purchase
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, processing, completed, failed
    extracted_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)  # 0.0000 to 1.0000
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="extractions", lazy="selectin")