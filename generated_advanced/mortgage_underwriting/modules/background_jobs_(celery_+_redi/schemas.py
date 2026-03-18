from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal  # FIXED: Added Decimal import for financial values


class JobExecutionBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    job_id: str = Field(..., description="Unique job execution identifier (UUID)")
    task_name: str = Field(..., description="Name of the scheduled task")
    status: str = Field(..., description="Current status of job execution")
    started_at: datetime = Field(..., description="When job started executing")
    completed_at: Optional[datetime] = Field(None, description="When job completed (null if still running)")
    runtime_seconds: Optional[Decimal] = Field(None, description="Total execution time in seconds")  # FIXED: Changed to Decimal for financial precision
    result_summary: Optional[str] = Field(None, description="Brief summary of job outcome")
    error_code: Optional[str] = Field(None, description="Error code if job failed")


class JobExecutionDetail(JobExecutionBase):
    args: Optional[List[str]] = Field(None, description="Arguments passed to job (PII redacted)")
    kwargs: Optional[Dict[str, Any]] = Field(None, description="Keyword arguments passed to job (PII redacted)")  # FIXED: More specific typing
    traceback: Optional[str] = Field(None, description="Full error traceback if job failed")
    retry_count: int = Field(..., description="Number of times job was retried")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class JobExecutionListResponse(BaseModel):
    items: List[JobExecutionBase]
    total: int
    limit: int
    offset: int