from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


class HealthStatus(str):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentStatus(str):
    UP = "up"
    DOWN = "down"


class ComponentHealth(BaseModel):
    status: ComponentStatus = Field(..., description="Component availability status")
    latency_ms: Optional[Decimal] = Field(None, description="Latency in milliseconds", gt=0)
    last_error: Optional[str] = Field(None, description="Last error message if any")


class HealthResponse(BaseModel):
    status: HealthStatus = Field(..., description="Overall service health status")
    version: str = Field(..., description="Service version identifier", max_length=50)
    uptime_seconds: int = Field(..., description="Service uptime in seconds", ge=0)
    checks: Dict[str, bool] = Field(..., description="Individual health check results")
    timestamp: datetime = Field(..., description="Timestamp of health check")


class DependencyHealthResponse(BaseModel):
    status: HealthStatus = Field(..., description="Overall dependency health status")
    database: ComponentHealth = Field(..., description="Database health information")
    redis: ComponentHealth = Field(..., description="Redis health information")
    minio: ComponentHealth = Field(..., description="MinIO health information")


class DeploymentHealthCreate(BaseModel):
    service_name: str = Field(..., max_length=100, description="Name of the service being checked")
    status: HealthStatus = Field(..., description="Health status of the service")
    version: Optional[str] = Field(None, max_length=50, description="Service version")
    uptime_seconds: Optional[int] = Field(None, description="Uptime in seconds", ge=0)
    details: Optional[str] = Field(None, description="Additional health check details")


class DeploymentHealthResponse(DeploymentHealthCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(..., description="Unique identifier for the health check record")
    timestamp: datetime = Field(..., description="Timestamp when health check was recorded")
    created_at: datetime = Field(..., description="Record creation timestamp")


class DependencyHealthCreate(BaseModel):
    deployment_id: int = Field(..., description="ID of associated deployment health check", gt=0)
    component_name: str = Field(..., max_length=50, description="Name of the component (db, redis, minio)")
    status: ComponentStatus = Field(..., description="Component status (up/down)")
    latency_ms: Optional[Decimal] = Field(None, description="Component latency in milliseconds", gt=0)
    last_error: Optional[str] = Field(None, description="Last error encountered")


class DependencyHealthResponseDetail(DependencyHealthCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(..., description="Unique identifier for dependency health record")
    checked_at: datetime = Field(..., description="Timestamp when dependency was checked")
    created_at: datetime = Field(..., description="Record creation timestamp")