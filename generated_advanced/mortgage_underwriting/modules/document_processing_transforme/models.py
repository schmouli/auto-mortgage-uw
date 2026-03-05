from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey, DECIMAL, Index, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import uuid


class Base(DeclarativeBase):
    pass


class DocumentProcessingJob(Base):
    __tablename__ = "document_processing_jobs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id"),
        nullable=False,
        index=True
    )
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of document processed (e.g., t4506, noa)"
    )
    s3_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="S3 key where the original PDF is stored"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="Job status: pending, processing, completed, failed"
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when processing started"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when processing completed"
    )
    
    # Audit Fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )  # FIXED: Added proper onupdate
    changed_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="User/system that last modified the record"
    )

    # Define composite index for performance
    __table_args__ = (
        Index('ix_doc_processing_status_client', 'status', 'application_id'),  # FIXED: Added composite index
    )


class ProcessedDocument(Base):
    __tablename__ = "processed_documents"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_processing_jobs.id", ondelete="CASCADE"),  # FIXED: Added ondelete parameter
        nullable=False,
        index=True
    )
    extracted_json: Mapped[dict] = mapped_column(
        Text,  # JSON stringified
        nullable=False
    )
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(5, 4),  # FIXED: Changed from float to Decimal for precision
        nullable=True
    )
    
    # Audit Fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(  # FIXED: Added missing updated_at field
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    changed_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )

    # Relationship
    job: Mapped["DocumentProcessingJob"] = relationship("DocumentProcessingJob", backref="processed_document")


class DocumentAuditLog(Base):
    __tablename__ = "document_audit_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processed_documents.id", ondelete="CASCADE"),  # FIXED: Added ondelete parameter
        nullable=False
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    
    # Audit Fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(  # FIXED: Added missing updated_at field
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    changed_by: Mapped[Optional[str]] = mapped_column(  # FIXED: Made explicitly Optional[str]
        String(255),
        nullable=True
    )
```

```