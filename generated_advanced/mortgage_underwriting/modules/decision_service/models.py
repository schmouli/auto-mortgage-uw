from datetime import datetime
from decimal import Decimal
from sqlalchemy import Index, Numeric, String, DateTime, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from typing import List, Dict, Any
from uuid import UUID

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class DecisionRecord(Base):
    """Underwriting decision record with full audit trail.
    
    Complies with OSFI B-20 (stress testing), FINTRAC (audit trail),
    CMHC (insurance logic), and PIPEDA (encrypted PII).
    """

    __tablename__ = "decision_records"
    __table_args__ = (
        Index("ix_decision_records_application_id", "application_id"),
        Index("ix_decision_records_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    application_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # approved, declined, exception, conditional
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    
    # Financial ratios
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    
    # CMHC insurance
    cmhc_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    stress_test_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    
    # Metadata
    policy_flags: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    exceptions: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    audit_trail: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())