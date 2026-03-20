from enum import Enum
from typing import Dict, List
from pydantic import BaseModel, Field

class EnvironmentEnum(str, Enum):
    dev = "dev"
    staging = "staging"
    prod = "prod"

class MigrationApplyRequest(BaseModel):
    revision: str = Field(default="head", description="Alembic revision to apply (e.g., 'head', '-1', or specific ID)")

class MigrationStatusResponse(BaseModel):
    current_rev: str = Field(..., description="Current database revision")
    pending: List[str] = Field(..., description="List of pending revisions")

class MigrationApplyResponse(BaseModel):
    status: str = Field(..., description="Migration status (ok/error)")
    revision: str = Field(..., description="Applied revision ID")

class SeedRequest(BaseModel):
    confirm: bool = Field(..., description="Confirmation flag to proceed with seeding")
    truncate_first: bool = Field(default=False, description="Whether to truncate tables before seeding")

class SeedResponse(BaseModel):
    status: str = Field(..., description="Seeding status (ok/error)")
    seeded: Dict[str, int] = Field(..., description="Summary of seeded entities count")

class RollbackTestRequest(BaseModel):
    test_scenario: str = Field(..., description="Scenario to test rollback on")

class RollbackTestResponse(BaseModel):
    status: str = Field(..., description="Rollback test status (ok/error)")
    rollback_verified: bool = Field(..., description="Whether rollback was successfully verified")