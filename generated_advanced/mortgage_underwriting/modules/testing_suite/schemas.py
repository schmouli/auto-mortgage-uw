from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class TestScenarioBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Unique identifier for the test scenario")
    description: str = Field(..., description="Human-readable description of the scenario")
    count: int = Field(..., ge=1, le=1000, description="Number of entities to seed")


class TestScenarioCreate(TestScenarioBase):
    pass


class TestScenarioResponse(TestScenarioBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: datetime


class TestDataSeedRequest(BaseModel):
    scenario: str = Field(..., description="Name of predefined test scenario")
    count: int = Field(default=None, ge=1, le=100, description="Override default count if needed (optional)")
    include_audit_trail: bool = Field(default=True, description="Whether to generate audit logs for seeded data")
    encrypt_pii: bool = Field(default=True, description="Whether to encrypt PII fields")


class TestDataSeedResponse(BaseModel):
    scenario: str
    created_applications: int
    test_data_id: str = Field(..., description="ID of this test run for reference and cleanup")
    cleanup_token: str = Field(..., description="Token required to clean up this test data")


class TestDataCleanupRequest(BaseModel):
    cleanup_token: str = Field(..., description="Token issued during seeding")


class TestDataCleanupResponse(BaseModel):
    deleted_entities: int
    message: str