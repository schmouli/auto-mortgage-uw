```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class BackgroundJobBase(BaseModel):
    job_name: str = Field(..., max_length=100, description="Unique name of the background job")
    description: Optional[str] = Field(None, description="Description of the job")
    cron_expression: str = Field(..., max_length=100, description="Cron expression for scheduling")
    is_active: bool = Field(True, description="Whether the job is currently active")


class BackgroundJobCreate(BackgroundJobBase):
    pass


class BackgroundJobUpdate(BaseModel):
    job_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    cron_expression: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class BackgroundJobResponse(BackgroundJobBase):
    id: int
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    changed_by: Optional[str]

    class Config:
        from_attributes = True
```