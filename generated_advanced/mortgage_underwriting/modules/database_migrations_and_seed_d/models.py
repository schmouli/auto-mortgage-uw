from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base
from datetime import datetime

class MigrationStatus(Base):
    __tablename__ = "migration_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    revision: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class SeedDataRecord(Base):
    __tablename__ = "seed_data_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # development|staging|demo
    record_type: Mapped[str] = mapped_column(String(50), nullable=False)  # users|lenders|products etc.
    count_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    triggered_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[Optional["User"]] = relationship("User")