from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy import Integer, String, DateTime, Text, Boolean, Index
from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base


class LenderPolicy(Base):
    __tablename__ = 'lender_policies'
    __table_args__ = (
        Index('idx_lender_policy_lender_id', 'lender_id'),
        Index('idx_lender_policy_is_active', 'is_active'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lender_id: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    lender_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    policy_xml: Mapped[str] = mapped_column(Text, nullable=False)
    xml_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # SHA256 hash
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)  # Hashed user ID
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f'<LenderPolicy(lender_id={self.lender_id}, version={self.version})>'