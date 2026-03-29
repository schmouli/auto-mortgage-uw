from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field, ConfigDict


class TestScenarioBase(BaseModel):
    """Base test scenario schema."""
    name: str = Field(..., min_length=1, max_length=255, description="Name of the test scenario")
    description: Optional[str] = Field(None, max_length=2000, description="Description of the test scenario")
    test_type: str = Field(..., pattern="^(unit|integration|e2e)$", description="Type of test")
    fixture_ids: Optional[List[int]] = Field(None, description="List of fixture IDs to use in this test")
    expected_outcomes: Optional[Dict[str, Any]] = Field(None, description="Expected test outcomes")


class TestScenarioCreate(TestScenarioBase):
    """Schema for creating a test scenario."""
    pass


class TestScenarioUpdate(BaseModel):
    """Schema for updating a test scenario."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    test_type: Optional[str] = Field(None, pattern="^(unit|integration|e2e)$")
    fixture_ids: Optional[List[int]] = None
    expected_outcomes: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class TestScenarioResponse(TestScenarioBase):
    """Schema for test scenario response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime


class TestExecuteRequest(BaseModel):
    """Schema for executing a test scenario."""
    environment: str = Field(..., pattern="^(dev|staging|prod)$", description="Environment to execute tests in")
    coverage_threshold: Optional[Decimal] = Field(None, ge=0, le=100, description="Minimum required coverage percentage")


class TestExecutionBase(BaseModel):
    """Base test execution schema."""
    scenario_id: int = Field(..., gt=0, description="ID of the test scenario being executed")
    environment: str = Field(..., pattern="^(dev|staging|prod)$", description="Environment where test was executed")


class TestExecutionCreate(TestExecutionBase):
    """Schema for creating a test execution record."""
    execution_id: str = Field(..., description="Unique identifier for this execution")
    status: str = Field("pending", pattern="^(pending|running|completed|failed)$")


class TestExecutionUpdate(BaseModel):
    """Schema for updating a test execution record."""
    status: Optional[str] = Field(None, pattern="^(pending|running|completed|failed)$")
    coverage_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    results: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TestExecutionResponse(TestExecutionBase):
    """Schema for test execution response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    execution_id: str
    status: str
    coverage_percentage: Optional[Decimal]
    results: Optional[Dict[str, Any]]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime


class TestExecutionDetail(TestExecutionResponse):
    """Detailed schema for test execution with full results."""
    pass


class TestFixtureBase(BaseModel):
    """Base test fixture schema."""
    name: str = Field(..., min_length=1, max_length=255, description="Name of the test fixture")
    data_type: str = Field(..., pattern="^(json|xml|binary)$", description="Type of data in the fixture")
    pii_markers: Optional[List[str]] = Field(None, description="Fields in the fixture that contain PII")


class TestFixtureCreate(TestFixtureBase):
    """Schema for creating a test fixture."""
    encrypted_payload: str = Field(..., description="AES-256 encrypted payload")


class TestFixtureUpdate(BaseModel):
    """Schema for updating a test fixture."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    data_type: Optional[str] = Field(None, pattern="^(json|xml|binary)$")
    encrypted_payload: Optional[str] = None
    pii_markers: Optional[List[str]] = None
    is_active: Optional[bool] = None


class TestFixtureResponse(TestFixtureBase):
    """Schema for test fixture response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime


class TestFixtureData(BaseModel):
    """Schema for decrypted test fixture data."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    decrypted_data: Dict[str, Any] = Field(..., description="Decrypted fixture data")