from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict
from pydantic import BaseModel, Field, ConfigDict

class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class DeploymentStatus(str, Enum):
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"

class ServiceHealthBase(BaseModel):
    service_name: str = Field(..., max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    status: ServiceStatus
    response_time_ms: Optional[Decimal] = Field(None, ge=0, le=99999999.99)
    error_code: Optional[str] = Field(None, max_length=50)
    details: Optional[str] = Field(None, max_length=1000)

class ServiceHealthCreate(ServiceHealthBase):
    pass

class ServiceHealthUpdate(ServiceHealthBase):
    pass

class ServiceHealthResponse(ServiceHealthBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    created_at: datetime
    updated_at: datetime

class DeploymentLogBase(BaseModel):
    service_name: str = Field(..., max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    version: str = Field(..., max_length=50, pattern=r'^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)*$')
    status: DeploymentStatus
    initiated_by: Optional[int] = None
    deployment_time: Optional[datetime] = None
    rollback_version: Optional[str] = Field(None, max_length=50, pattern=r'^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)*$')
    error_details: Optional[str] = Field(None, max_length=2000)

class DeploymentLogCreate(DeploymentLogBase):
    pass

class DeploymentLogUpdate(DeploymentLogBase):
    pass

class DeploymentLogResponse(DeploymentLogBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime

class HealthCheckResponse(BaseModel):
    status: ServiceStatus
    timestamp: datetime
    services: Dict[str, ServiceHealthResponse]

class RestartServiceRequest(BaseModel):
    force: bool = False