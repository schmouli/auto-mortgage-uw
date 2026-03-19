from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text, CheckConstraint, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from sqlalchemy.sql import func
from mortgage_underwriting.common.database import Base


class TestScenario(Base):
    """Predefined test scenarios for seeding synthetic data.
    
    Each scenario represents a specific compliance or business case.
    """
    __tablename__ = "test_scenarios"
    __table_args__ = (
        CheckConstraint("count >= 1 AND count <= 1000", name="check_valid_count"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class TestDataRun(Base):
    """Record of each test data seeding operation.
    
    Used for cleanup and audit purposes in non-production environments.
    """
    __tablename__ = "test_data_runs"
    __table_args__ = (
        Index("ix_test_run_scenario", "scenario_name"),
        Index("ix_test_run_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # UUID-like identifier
    scenario_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_entities: Mapped[int] = mapped_column(Integer, nullable=False)
    cleanup_token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    creator: Mapped[Optional["User"]] = relationship("User")  # type: ignore