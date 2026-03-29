from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from sqlalchemy import Integer, String, Text, DateTime, Boolean, Index, ForeignKey
from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class LenderPolicy(Base):
    __tablename__ = "lender_policies"
    __table_args__ = (
        Index('ix_lender_policies_lender_id', 'lender_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lender_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    xml_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    evaluations: Mapped[list["PolicyEvaluation"]] = relationship("PolicyEvaluation", back_populates="policy")


class PolicyEvaluation(Base):
    __tablename__ = "policy_evaluations"
    __table_args__ = (
        Index('ix_policy_evaluations_policy_id', 'policy_id'),
        Index('ix_policy_evaluations_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("lender_policies.id"), nullable=False)
    application_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON serialized
    result: Mapped[bool] = mapped_column(Boolean, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    policy: Mapped["LenderPolicy"] = relationship("LenderPolicy", back_populates="evaluations")