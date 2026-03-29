from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class DeploymentStrategy(str, Enum):
    ROLLING = "rolling"
    BLUE_GREEN = "blue-green"
    RECREATE = "recreate"


class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    PENDING = "pending"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class DeploymentBase(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=100)
    version: str = Field(..., min_length=1, max_length=50)
    strategy: DeploymentStrategy


class DeploymentCreate(DeploymentBase):
    pass


class DeploymentResponse(DeploymentBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    status: str
    logs: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class DeploymentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    deployment_id: int
    status: str
    logs: Optional[List[str]] = None


class ServiceHealthCheckBase(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=100)
    status: ServiceStatus
    latency_ms: Optional[Decimal] = None
    details: Optional[str] = None


class ServiceHealthCheckCreate(ServiceHealthCheckBase):
    pass


class ServiceHealthCheckResponse(ServiceHealthCheckBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    checked_at: datetime
    created_at: datetime


class ServicesHealthOverviewResponse(BaseModel):
    status: str
    services: List[ServiceHealthCheckResponse]