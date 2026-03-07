from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class MigrationStatusEnum(str, Enum):
    up_to_date = "up_to_date"
    pending = "pending"
    error = "error"

class MigrationStatusResponse(BaseModel):
    current_revision: str = Field(..., description="Current database revision")
    head_revision: str = Field(..., description="Head revision in codebase")
    pending_migrations: int = Field(..., ge=0, description="Number of pending migrations")
    last_applied: Optional[datetime] = Field(None, description="Timestamp of last applied migration")
    status: MigrationStatusEnum = Field(..., description="Overall migration health status")

class SeedExecutionRequest(BaseModel):
    environment: str = Field(..., pattern="^(dev|staging|prod)$", description="Target deployment environment")
    dry_run: bool = Field(False, description="Preview changes without applying them")
    force: bool = Field(False, description="Force execution even if already seeded")
    scenario: str = Field("approved", pattern="^(approved|declined|conditional)$", description="Underwriting outcome scenario")

class SeedExecutionResponse(BaseModel):
    executed: bool = Field(..., description="Whether seeding was executed or skipped")
    message: str = Field(..., description="Human-readable result summary")
    items_created: Dict[str, int] = Field(default_factory=dict, description="Count of created items by type")