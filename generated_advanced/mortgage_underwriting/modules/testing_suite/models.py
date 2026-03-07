from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, ForeignKey, Numeric, Boolean, Text, Index, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base

class TestRun(Base):
    """Test execution metadata for audit and compliance.
    
    Stores results of test runs for regulatory reporting and quality assurance.
    """
    __tablename__ = "test_runs"
    __table_args__ = (
        Index('ix_test_runs_timestamp', 'timestamp'),
        Index('ix_test_runs_branch', 'branch'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), unique=True, nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    branch: Mapped[str] = mapped_column(String(100), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    coverage_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tests_passed: Mapped[int] = mapped_column(Integer, nullable=False)
    tests_failed: Mapped[int] = mapped_column(Integer, nullable=False)
    compliance_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<TestRun(id={self.id}, run_id='{self.run_id}', passed={self.tests_passed}, failed={self.tests_failed})>"