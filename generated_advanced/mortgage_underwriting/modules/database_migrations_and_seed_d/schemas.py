from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel, Field, ConfigDict

class MigrationStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    revision: str
    applied_at: datetime

class SeedTriggerRequest(BaseModel):
    confirm: bool = Field(..., description="Must explicitly confirm seeding operation")
    truncate_existing: bool = Field(False, description="Truncate tables before seeding (dev only)")

class SeedTriggerResponse(BaseModel):
    status: str = Field(..., example="success")
    environment: str = Field(..., example="development")
    records_created: Dict[str, int]
    execution_time_ms: int

class SeedHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    environment: str
    record_type: str
    count_inserted: int
    execution_time_ms: int
    triggered_by: Optional[int]
    created_at: datetime