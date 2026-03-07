from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field, ConfigDict, field_validator
import re

def validate_cron_expression(cron: str) -> str:
    """Basic cron expression validator."""
    # This is a simplified validator - in practice you might want a more robust one
    if not re.match(r'^[\*0-9/,\-\s]+$', cron):
        raise ValueError('Invalid cron expression format')
    return cron

# Job Execution Log Schemas

class JobExecutionLogBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    task_id: str = Field(..., max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    task_name: str = Field(..., max_length=100, pattern=r'^[a-zA-Z0-9_.:-]+$')
    status: str = Field(..., pattern="^(pending|running|success|failure|retry)$")
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = Field(None, max_length=2000)
    is_manual_trigger: bool = False
    triggered_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

class JobExecutionLogResponse(JobExecutionLogBase):
    id: int
    traceback: Optional[str] = Field(None, max_length=10000)
    args: Optional[Dict[str, Any]] = None
    kwargs: Optional[Dict[str, Any]] = None

# Scheduled Job Schemas

class ScheduledJobBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    task_name: str = Field(..., max_length=100, pattern=r'^[a-zA-Z0-9_.:-]+$')
    cron_expression: str = Field(..., max_length=100)
    description: str = Field(..., max_length=500)
    is_active: bool = True
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    @field_validator('cron_expression')
    @classmethod
    def validate_cron(cls, v: str) -> str:
        return validate_cron_expression(v)

class ScheduledJobResponse(ScheduledJobBase):
    id: int

class ScheduledJobListResponse(BaseModel):
    schedules: List[ScheduledJobResponse]

# Trigger Job Schemas

class JobTriggerRequest(BaseModel):
    task_name: str = Field(..., description="Name of the task to trigger", max_length=100, pattern=r'^[a-zA-Z0-9_.:-]+$')
    run_immediately: bool = Field(False, description="Run immediately or wait for next scheduled execution")
    params: Optional[Dict[str, Any]] = Field(None, description="Optional parameters for the task")

class JobTriggerResponse(BaseModel):
    task_id: str = Field(..., description="ID of the triggered task", max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    status: str = Field(..., description="Current status of the task", pattern="^(pending|running|success|failure|retry|queued)$")
    scheduled_at: datetime = Field(..., description="When the task is scheduled to run")

# Job Status Schemas

class JobStatusResponse(BaseModel):
    task_id: str = Field(..., description="ID of the task", max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    task_name: str = Field(..., description="Name of the task", max_length=100, pattern=r'^[a-zA-Z0-9_.:-]+$')
    status: str = Field(..., description="Current status of the task", pattern="^(pending|running|success|failure|retry)$")
    started_at: Optional[datetime] = Field(None, description="When the task started running")
    completed_at: Optional[datetime] = Field(None, description="When the task completed")
    result: Optional[Dict[str, Any]] = Field(None, description="Result of the task execution")
    error: Optional[str] = Field(None, description="Error message if task failed", max_length=2000)