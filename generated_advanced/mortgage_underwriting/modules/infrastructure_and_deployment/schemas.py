from pydantic import BaseModel, Field, ConfigDict, field_validator, PositiveInt
from datetime import datetime
from typing import Optional


class InfrastructureProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    is_active: bool = True


class InfrastructureProviderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    is_active: Optional[bool] = None


class InfrastructureProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DeploymentEventCreate(BaseModel):
    provider_id: int = Field(..., gt=0)
    event_type: str = Field(..., min_length=1, max_length=100)
    status: str = Field(..., min_length=1, max_length=50)
    details: Optional[str] = None


class DeploymentEventUpdate(BaseModel):
    event_type: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[str] = Field(None, min_length=1, max_length=50)
    details: Optional[str] = None


class DeploymentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    provider_id: int
    event_type: str
    status: str
    details: Optional[str]
    created_at: datetime
    updated_at: datetime


class DeploymentAuditCreate(BaseModel):
    deployment_event_id: int = Field(..., gt=0)
    action: str = Field(..., min_length=1, max_length=100)
    performed_by: str = Field(..., min_length=1, max_length=255)
    notes: Optional[str] = None


class DeploymentAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    deployment_event_id: int
    action: str
    performed_by: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class DeploymentListQueryParams(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    skip: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of items to return")
    provider_id: Optional[int] = Field(None, gt=0, description="Filter by provider ID")
```

```