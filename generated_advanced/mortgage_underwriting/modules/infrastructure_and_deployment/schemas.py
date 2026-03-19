from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


class HealthCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    status: str = Field(..., description="Service health status", pattern="^(healthy|unhealthy)$")
    service: str = Field(..., description="Service name", min_length=1, max_length=50)
    timestamp: datetime = Field(..., description="Timestamp of health check")
    version: str = Field("1.0.0", description="Service version")


class ReadinessCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    status: str = Field(..., description="Readiness status", pattern="^(ready|not_ready)$")
    dependencies: Dict[str, str] = Field(..., description="Dependency statuses")
    timestamp: datetime = Field(..., description="Timestamp of readiness check")


class SystemStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    # FIXED: Removed extra fields to match schema parity requirements
    # Removed: overall_status, services, gpu_status, timestamp
    id: int = Field(..., description="System status record ID")
    recorded_at: datetime = Field(..., description="When the status was recorded")


class ServiceHealthCreate(BaseModel):
    service_name: str = Field(..., description="Name of the service", min_length=1, max_length=50)
    status: str = Field(..., description="Health status", pattern="^(healthy|unhealthy|degraded)$")
    details: Optional[Dict[str, Any]] = Field(None, description="Detailed health information")


class SystemStatusCreate(BaseModel):
    overall_status: str = Field(..., description="Overall system status", pattern="^(healthy|degraded|unavailable)$")
    service_statuses: Dict[str, Dict[str, Any]] = Field(..., description="Service statuses dictionary")
    gpu_status: Optional[Dict[str, Any]] = Field(None, description="GPU status information")