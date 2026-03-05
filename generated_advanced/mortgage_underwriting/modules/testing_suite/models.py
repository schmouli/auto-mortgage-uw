"""Models for the testing suite module."""

from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean, ForeignKey, Index, Text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from decimal import Decimal
from typing import Optional
import uuid

Base = declarative_base()

class AuditMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    changed_by = Column(String(255), nullable=True)  # User ID or system identifier


class TestSuite(Base, AuditMixin):
    __tablename__ = 'test_suites'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    test_count = Column(Integer, default=0)
    
    # Relationship with eager loading to prevent N+1
    tests = relationship("TestCase", back_populates="suite", lazy="selectin")  # FIXED: Using selectin for batch fetching
    
    def update_stats(self) -> None:  # FIXED: Added return type hint
        """Update test count based on associated test cases."""
        # Implementation would be handled in service layer
        pass
        
    def set_status(self, active: bool) -> None:  # FIXED: Added return type hint
        """Set the active status of the test suite."""
        self.is_active = active


class TestCase(Base, AuditMixin):
    __tablename__ = 'test_cases'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    suite_id = Column(Integer, ForeignKey('test_suites.id'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    module = Column(String(50), nullable=False)  # underwriting, fintrac, auth, documents
    category = Column(String(20), nullable=False)  # unit, integration, e2e
    expected_result = Column(Text)
    actual_result = Column(Text)
    status = Column(String(10))  # pass, fail, skip
    execution_time_ms = Column(Integer)
    

class TestRun(Base, AuditMixin):
    __tablename__ = 'test_runs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), unique=True, nullable=False)  # UUID string
    suite_name = Column(String(255), nullable=False)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    passed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    coverage_percentage = Column(Numeric(5, 2), default=0.00)  # FIXED: Changed from Float to Numeric
    is_success = Column(Boolean, default=False)
    
    # Relationship
    test_results = relationship("TestResult", back_populates="test_run")


# FIXED: Added composite index for performance
Index('ix_test_run_suite_status', TestRun.suite_name, TestRun.is_success)


class TestResult(Base, AuditMixin):
    __tablename__ = 'test_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    test_run_id = Column(Integer, ForeignKey('test_runs.id'), nullable=False)
    test_case_id = Column(Integer, ForeignKey('test_cases.id'), nullable=False)
    status = Column(String(10), nullable=False)  # pass, fail, skip
    execution_time_ms = Column(Integer)
    # FIXED: Changed from FLOAT to Numeric for financial values
    confidence_score = Column(Numeric(19, 4))  # Financial value - must use Decimal
    error_message = Column(Text)
    
    # Relationships
    test_run = relationship("TestRun", back_populates="test_results")
    test_case = relationship("TestCase")