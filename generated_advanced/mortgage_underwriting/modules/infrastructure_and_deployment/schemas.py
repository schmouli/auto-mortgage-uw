from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict
from pydantic import BaseModel, Field, ConfigDict


# Health Check Schemas

class HealthCheckComponent(BaseModel):
    status: str = Field(..., pattern="^(ok|error)$")
    latency_ms: Optional[Decimal] = Field(None, ge=0)
    memory_utilization: Optional[Decimal] = Field(None, ge=0, le=100)  # GPU only

    model_config = ConfigDict(from_attributes=True)


class HealthCheckResponse(BaseModel):
    status: str = Field(..., pattern="^(healthy|degraded|unhealthy)$")
    timestamp: datetime
    checks: Dict[str, HealthCheckComponent]
    version: str = Field(..., description="Git commit SHA")

    model_config = ConfigDict(from_attributes=True)

# Deployment Status Schemas

class DeploymentStatusResponse(BaseModel):
    deployment_id: str = Field(..., description="UUID of the deployment")
    service_name: str = Field(..., description="Name of the service being deployed")
    status: str = Field(..., pattern="^(pending|deploying|success|failed|rolled_back)$")
    version: str = Field(..., description="Deployment version tag")
    message: Optional[str] = Field(None, description="Human-readable status message")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DeploymentRollbackRequest(BaseModel):
    deployment_id: str = Field(..., description="UUID of the deployment to rollback")
    reason: str = Field(..., min_length=5, max_length=500, description="Reason for rollback")

# Generic Response

class SimpleMessageResponse(BaseModel):
    detail: str
    
    model_config = ConfigDict(from_attributes=True)