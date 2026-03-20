from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, Text, Boolean, Index, ForeignKey, Numeric
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy.sql import func

if TYPE_CHECKING:
    from mortgage_underwriting.modules.policy.models import PolicyEvaluation

from mortgage_underwriting.common.database import Base

class LenderPolicy(Base):
    """XML-based lender policy configuration.
    
    Stores parsed MISMO 3.0 compliant XML policies with audit tracking.
    """
    __tablename__ = "lender_policies"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lender_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    xml_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    evaluations: Mapped[list["PolicyEvaluation"]] = relationship("PolicyEvaluation", back_populates="policy")
    
    __table_args__ = (
        Index('idx_lender_policy_active', 'lender_id', 'is_active'),
    )


class PolicyEvaluation(Base):
    """Policy evaluation result for an application.
    
    Immutable record of policy checks with detailed breakdown.
    """
    __tablename__ = "policy_evaluations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("lender_policies.id"), nullable=False)
    application_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    details: Mapped[Dict[str, Any]] = mapped_column(Text, nullable=False)  # JSON-encoded dict
    evaluated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    policy: Mapped["LenderPolicy"] = relationship("LenderPolicy", back_populates="evaluations")