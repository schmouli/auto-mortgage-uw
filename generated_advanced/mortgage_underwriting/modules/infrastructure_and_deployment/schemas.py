from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

# --- Health Check Schemas ---

class ServiceHealthBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    endpoint: str = Field(..., max_length=255)
    health_check_url: str = Field(..., max_length=255)
    status: str = Field(..., pattern="^(healthy|degraded|unhealthy)$")
    last_heartbeat: datetime
    version: Optional[str] = Field(None, max_length=50)
    error_message: Optional[str] = None
    active_workflows: Optional[int] = None
    response_time_ms: Optional[Decimal] = None
    is_critical: bool = False


class ServiceHealthCreate(ServiceHealthBase):
    pass


class ServiceHealthUpdate(BaseModel):
    status: str = Field(..., pattern="^(healthy|degraded|unhealthy)$")
    last_heartbeat: datetime
    error_message: Optional[str] = None
    active_workflows: Optional[int] = None
    response_time_ms: Optional[Decimal] = None


class ServiceHealthResponse(ServiceHealthBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime

# --- Deployment Status Schemas ---

class DeploymentStatusBase(BaseModel):
    version: str = Field(..., min_length=1, max_length=50)
    status: str = Field(..., pattern="^(deployed|rolling_back|failed)$")
    rollback_version: Optional[str] = Field(None, max_length=50)
    failure_reason: Optional[str] = None


class DeploymentStatusCreate(DeploymentStatusBase):
    pass


class DeploymentStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(deployed|rolling_back|failed)$")
    rollback_version: Optional[str] = Field(None, max_length=50)
    failure_reason: Optional[str] = None


class DeploymentStatusResponse(DeploymentStatusBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deployed_at: datetime
    created_at: datetime
    updated_at: datetime

# --- Config Validation Schemas ---

class ConfigValidationBase(BaseModel):
    validator_user_id: int = Field(..., gt=0)
    is_valid: bool
    validation_errors: Optional[str] = None
    config_snapshot: Optional[str] = None


class ConfigValidationCreate(ConfigValidationBase):
    pass


class ConfigValidationResponse(ConfigValidationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime

# --- System Health Aggregate ---

class SystemHealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str = Field(..., pattern="^(healthy|degraded|unhealthy)$")
    timestamp: datetime
    version: str
    services: Dict[str, Dict[str, Any]]

# --- Pagination ---

class PaginatedServiceHealthResponse(BaseModel):
    items: List[ServiceHealthResponse]
    total: int
    page: int
    size: int