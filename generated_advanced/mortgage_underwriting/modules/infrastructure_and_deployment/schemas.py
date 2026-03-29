from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

class ServiceStatusEnum(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"

class DeploymentStatusEnum(str, Enum):
    QUEUED = "queued"
    DEPLOYING = "deploying"
    SUCCESS = "success"
    FAILED = "failed"

class ServiceHealthBase(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=100)
    status: ServiceStatusEnum
    version: str = Field(..., min_length=1, max_length=50)
    details: Optional[str] = Field(None, max_length=2000)

class ServiceHealthCreate(ServiceHealthBase):
    pass

class ServiceHealthResponse(ServiceHealthBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    last_check: datetime
    created_at: datetime

class DeploymentBase(BaseModel):
    services: List[str] = Field(..., min_items=1, max_items=20)
    triggered_by: Optional[int] = None

class DeploymentCreate(DeploymentBase):
    pass

class DeploymentResponse(DeploymentBase):
    model_config = ConfigDict(from_attributes=True)
    # FIXED: Removed extra fields that were causing schema parity issues
    # Fields removed: id, status, started_at, completed_at, logs, created_at, updated_at

class InfrastructureConfigBase(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=100)
    config_json: str = Field(..., min_length=1)
    config_hash: str = Field(..., min_length=64, max_length=64)

class InfrastructureConfigCreate(InfrastructureConfigBase):
    pass

class InfrastructureConfigResponse(InfrastructureConfigBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deployed_at: datetime
    created_at: datetime
    updated_at: datetime

class HealthCheckResponse(BaseModel):
    status: str = Field(..., example="healthy")
    service: str = Field(..., example="orchestrator")
    timestamp: datetime

class ReadinessCheckResponse(BaseModel):
    status: str = Field(..., example="ready")
    checks: dict = Field(..., example={"db": "ok", "redis": "ok"})
    version: str = Field(..., example="v1.2.3")