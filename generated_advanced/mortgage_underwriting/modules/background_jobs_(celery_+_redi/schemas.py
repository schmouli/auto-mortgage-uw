from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal


class JobTriggerRequest(BaseModel):
    force: bool = Field(False, description="Skip schedule checks and run immediately")
    params: Dict[str, Any] = Field(default_factory=dict, description="Job-specific parameters")


class JobTriggerResponse(BaseModel):
    job_name: str
    task_id: str
    status: str = Field(..., pattern="^(queued|started)$")
    queued_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobExecutionStatus(BaseModel):
    task_id: str
    status: str = Field(..., pattern="^(success|failure|retrying|running)$")
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[Decimal] = None
    records_processed: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class JobStatusResponse(BaseModel):
    job_name: str
    is_enabled: bool
    schedule: str = Field(..., description="Cron expression")
    last_execution: Optional[JobExecutionStatus] = None
    next_scheduled_run: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)