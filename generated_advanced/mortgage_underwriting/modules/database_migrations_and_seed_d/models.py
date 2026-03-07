from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base

class MigrationStatus(Base):
    __tablename__ = "migration_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    revision: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<MigrationStatus(id={self.id}, revision='{self.revision}', is_current={self.is_current})>"