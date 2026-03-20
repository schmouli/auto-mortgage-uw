from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base

class Migration(Base):
    __tablename__ = "migrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    revision: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SeedData(Base):
    __tablename__ = "seed_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # dev, staging, prod
    seeded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    data_summary: Mapped[str] = mapped_column(Text)  # JSON summary of what was seeded
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())