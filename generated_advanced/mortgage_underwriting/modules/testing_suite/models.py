from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, DateTime, Text, Numeric, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any

from mortgage_underwriting.common.database import Base


class TestRun(Base):
    """Track execution of automated test suites with metadata."""
    __tablename__ = "test_runs"
    __table_args__ = (
        Index('ix_test_runs_module_name', 'module_name'),
        Index('ix_test_runs_started_at', 'started_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    module_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    test_suite_type: Mapped[str] = mapped_column(String(50), nullable=False)  # unit, integration, e2e
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # passed, failed, running
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    log_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    trigger_user: Mapped[Optional["User"]] = relationship("User")


class TestCase(Base):
    """Individual test case execution result within a test run."""
    __tablename__ = "test_cases"
    __table_args__ = (
        Index('ix_test_cases_run_id', 'run_id'),
        Index('ix_test_cases_test_name', 'test_name'),
        Index('ix_test_cases_status', 'status'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    test_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    test_class: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # passed, failed, skipped, error
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assertion_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    compliance_tags: Mapped[Optional[Dict[str, str]]] = mapped_column(JSONB, nullable=True)  # e.g., {"reg": "OSFI-B20"}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    test_run: Mapped["TestRun"] = relationship("TestRun", backref="test_cases")


class TestCoverageReport(Base):
    """Per-module static analysis and coverage metrics."""
    __tablename__ = "test_coverage_reports"
    __table_args__ = (
        Index('ix_test_coverage_reports_module_name', 'module_name'),
        Index('ix_test_coverage_reports_reported_at', 'reported_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    module_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    line_coverage_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    branch_coverage_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    function_coverage_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    missed_lines: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # comma-separated
    complexity_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    issues_found: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    security_findings: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)