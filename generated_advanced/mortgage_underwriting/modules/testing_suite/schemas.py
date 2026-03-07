from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

class TestRunBase(BaseModel):
    """Base schema for test run records."""
    branch: str = Field(..., max_length=100, description="Git branch name")
    commit_sha: str = Field(..., min_length=40, max_length=40, description="Full git commit SHA")
    coverage_percent: Decimal = Field(..., ge=0, le=100, description="Code coverage percentage")
    tests_passed: int = Field(..., ge=0, description="Number of tests that passed")
    tests_failed: int = Field(..., ge=0, description="Number of tests that failed")
    compliance_score: Decimal = Field(..., ge=0, le=100, description="Regulatory compliance score")


class TestRunCreate(TestRunBase):
    """Schema for creating a new test run record."""
    run_id: UUID = Field(..., description="Unique identifier for the test run")


class TestRunUpdate(BaseModel):
    """Schema for updating an existing test run record."""
    coverage_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    tests_passed: Optional[int] = Field(None, ge=0)
    tests_failed: Optional[int] = Field(None, ge=0)
    compliance_score: Optional[Decimal] = Field(None, ge=0, le=100)

    model_config = ConfigDict(validate_assignment=True)


class TestRunResponse(TestRunBase):
    """Schema for returning test run information."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    run_id: UUID
    timestamp: datetime
    created_at: datetime