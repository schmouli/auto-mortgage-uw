from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from sqlalchemy import String, Text, DateTime, Integer, Numeric, Boolean, Index
from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base

class LenderPolicy(Base):
    __tablename__ = 'lender_policies'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lender_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    lender_name: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='active', nullable=False)  # active, draft, deprecated
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    xml_content: Mapped[str] = mapped_column(Text, nullable=False)
    evaluations_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_lender_policy_status', 'status'),
        Index('idx_lender_policy_lender_id_status', 'lender_id', 'status'),
    )
    
    def __repr__(self) -> str:
        return f'<LenderPolicy(id={self.id}, lender_id="{self.lender_id}", version="{self.policy_version}")>'