from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime
from typing import Optional, List


class WorkflowCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    is_active: bool = True


class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    workflow_id: int
    name: str = Field(..., max_length=255)
    status: str = Field(default="pending", max_length=50)
    estimated_completion_time: Optional[Decimal] = Field(None, gt=0)


class TaskUpdate(BaseModel):
    workflow_id: Optional[int] = None
    name: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=50)
    estimated_completion_time: Optional[Decimal] = Field(None, gt=0)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    workflow_id: int
    name: str
    status: str
    estimated_completion_time: Optional[Decimal]
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    items: List[TaskResponse]
    total: int
    skip: int
    limit: int
```

```