from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator
import re


class JobBase(BaseModel):
    name: str = Field(..., max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    task_path: str = Field(..., max_length=255)
    cron_expression: str = Field(..., max_length=50)
    description: Optional[str] = Field(None, max_length=1000)
    args_json: Optional[str] = Field(None, max_length=5000)
    is_active: bool = True
    
    @field_validator('task_path')
    @classmethod
    def validate_task_path(cls, v: str) -> str:
        if not v or '.' not in v:
            raise ValueError('Task path must be a valid Python module path')
        return v
    
    @field_validator('cron_expression')
    @classmethod
    def validate_cron_expression(cls, v: str) -> str:
        # Basic cron expression validation
        if not v or len(v.split()) < 5:
            raise ValueError('Invalid cron expression format')
        return v


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100, pattern=r'^[a-zA-Z0-9_-]*$')
    task_path: Optional[str] = Field(None, max_length=255)
    cron_expression: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=1000)
    args_json: Optional[str] = Field(None, max_length=5000)
    is_active: Optional[bool] = None
    status: Optional[str] = Field(None, pattern="^(pending|running|success|failed)$")
    failure_reason: Optional[str] = Field(None, max_length=2000)
    
    @field_validator('task_path')
    @classmethod
    def validate_task_path(cls, v: str) -> str:
        if v is not None and (not v or '.' not in v):
            raise ValueError('Task path must be a valid Python module path')
        return v
    
    @field_validator('cron_expression')
    @classmethod
    def validate_cron_expression(cls, v: str) -> str:
        if v is not None and (not v or len(v.split()) < 5):
            raise ValueError('Invalid cron expression format')
        return v


class JobResponse(JobBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    status: str
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    failure_reason: Optional[str]
    scheduled_at: datetime
    created_at: datetime
    updated_at: datetime


class JobExecutionLog(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    job_id: int
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    output: Optional[str]
    error_message: Optional[str]
    created_at: datetime