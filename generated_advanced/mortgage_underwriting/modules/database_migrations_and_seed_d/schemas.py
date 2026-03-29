from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class MigrationRecordBase(BaseModel):
    version: str = Field(..., max_length=50, description="Alembic migration version identifier")
    description: str = Field(..., description="Brief description of what the migration does")


class MigrationRecordCreate(MigrationRecordBase):
    pass


class MigrationRecordUpdate(BaseModel):
    is_applied: bool = Field(..., description="Whether the migration has been successfully applied")


class MigrationRecordResponse(MigrationRecordBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    applied_at: Optional[datetime]
    is_applied: bool
    created_at: datetime
    updated_at: datetime