from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy import (

    Column, Integer, String, DateTime, Numeric, Boolean,
    ForeignKey, Index, Text, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        Index('ix_decisions_application_id', 'application_id'),
        Index('ix_decisions_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[UUID] = mapped_column(String(36), unique=True, index=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # approved, declined, exception
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    stress_test_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    cmhc_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_flags: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    exceptions: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    audit_trail: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    application: Mapped["Application"] = relationship("Application", back_populates="decision")  # Assuming Application model exists

    def __repr__(self) -> str:
        return f'<Decision(id={self.id}, application_id="{self.application_id}", decision="{self.decision}")>'