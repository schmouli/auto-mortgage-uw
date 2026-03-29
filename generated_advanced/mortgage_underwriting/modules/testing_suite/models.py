from datetime import datetime
from decimal import Decimal
from sqlalchemy import Index, Numeric, String, DateTime, Text, ForeignKey, Boolean, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any, List

from sqlalchemy.sql import func

from mortgage_underwriting.common.database import Base
# Import User model to avoid circular import issues
from mortgage_underwriting.modules.auth.models import User

class TestScenario(Base):
    """Test scenario definition for automated testing.
    
    Stores test configurations including name, description, test type,
    associated fixtures, and expected outcomes.
    """
    __tablename__ = "test_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    test_type: Mapped[str] = mapped_column(String(50), nullable=False)  # unit, integration, e2e
    fixture_ids: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)  # JSON array of fixture IDs
    expected_outcomes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # Expected results
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index('ix_test_scenarios_name', 'name'),
        Index('ix_test_scenarios_test_type', 'test_type'),
    )


class TestExecution(Base):
    """Test execution record tracking test runs.
    
    Records execution details including environment, coverage metrics,
    execution status, and results.
    """
    __tablename__ = "test_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("test_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)  # UUID
    environment: Mapped[str] = mapped_column(String(50), nullable=False)  # dev, staging, prod
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, running, completed, failed
    coverage_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    results: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # Detailed test results
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    scenario: Mapped["TestScenario"] = relationship("TestScenario", back_populates="executions")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index('ix_test_executions_execution_id', 'execution_id'),
        Index('ix_test_executions_scenario_id', 'scenario_id'),
        Index('ix_test_executions_environment', 'environment'),
        Index('ix_test_executions_status', 'status'),
    )


# Add relationship to TestScenario
TestScenario.executions = relationship("TestExecution", back_populates="scenario", cascade="all, delete-orphan")

class TestFixture(Base):
    """Test fixture containing reusable test data.
    
    Stores encrypted test data payloads with metadata about their usage
    and PII markers for compliance purposes.
    """
    __tablename__ = "test_fixtures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False)  # json, xml, binary
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)  # AES-256 encrypted
    pii_markers: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)  # Fields containing PII
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index('ix_test_fixtures_name', 'name'),
        Index('ix_test_fixtures_data_type', 'data_type'),
    )