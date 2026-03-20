from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, Numeric, Boolean, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Dict, Any

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class UnderwritingDecision(Base):
    """Immutable underwriting decision record with full audit trail.
    
    Complies with OSFI B-20 (stress testing), FINTRAC (>10k flagging),
    CMHC (insurance logic), and PIPEDA (data minimization).
    """
    __tablename__ = "underwriting_decisions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # approved, declined, exception
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    
    # Financial ratios
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    stress_test_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    
    # Flags
    cmhc_required: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_flags: Mapped[List[str]] = mapped_column(JSON, default=list)
    exceptions: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    
    # Audit
    audit_trail: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    model_version: Mapped[str] = mapped_column(String(20), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('ix_underwriting_decisions_application_id', 'application_id'),
        Index('ix_underwriting_decisions_decision', 'decision'),
        Index('ix_underwriting_decisions_created_at', 'created_at'),
    )


class DecisionAuditLog(Base):
    """Detailed audit trail for decision process steps.
    
    Required for OSFI B-20 ratio calculation transparency and
    FINTRAC 5-year record retention.
    """
    __tablename__ = "decision_audit_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    decision_id: Mapped[int] = mapped_column(Integer, ForeignKey("underwriting_decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    step: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    decision: Mapped["UnderwritingDecision"] = relationship("UnderwritingDecision", back_populates="audit_logs")
    
    __table_args__ = (
        Index('ix_decision_audit_logs_decision_id', 'decision_id'),
        Index('ix_decision_audit_logs_step', 'step'),
    )

UnderwritingDecision.audit_logs = relationship("DecisionAuditLog", back_populates="decision", cascade="all, delete-orphan")