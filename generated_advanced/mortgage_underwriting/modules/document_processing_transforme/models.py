```python
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey, DECIMAL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import uuid


class Base(DeclarativeBase):
    pass


class Extraction(Base):
    __tablename__ = "extractions"

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
    extracted_json: Mapped[dict] = mapped_column(
        Text,  # Using Text to store JSON string; actual parsing handled at service level
        nullable=False,
        comment="Structured extraction result in JSON format"
    )
    confidence: Mapped[Optional[Decimal]] = mapped_column(
        DECIMAL(precision=5, scale=4),
        nullable=True,
        comment="Model's confidence score for this extraction"
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Version identifier of the Donut model used"
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
    )
    changed_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="User/system that last modified the record"
    )

    def __repr__(self) -> str:
        return f"<Extraction(id={self.id}, document_type='{self.document_type}', application_id='{self.application_id}')>"
```