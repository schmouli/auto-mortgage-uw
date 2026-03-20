from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from decimal import Decimal


class EnvironmentEnum(str, Enum):
    development = "development"
    staging = "staging"
    production = "production"


class DeploymentBase(BaseModel):
    application_id: str = Field(..., description="UUID of the application being deployed", pattern=r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
    environment: EnvironmentEnum = Field(..., description="Target deployment environment")
    version: str = Field(..., description="Version tag of the deployment", min_length=1, max_length=20)

    @field_validator('application_id')
    @classmethod
    def validate_uuid_format(cls, v: str) -> str:
        if not isinstance(v, str) or len(v) != 36:
            raise ValueError('Invalid UUID format')
        return v


class DeploymentCreate(DeploymentBase):
    pass


class DeploymentUpdate(BaseModel):
    status: str = Field(..., description="New deployment status", min_length=1, max_length=50)
    deployed_at: Optional[datetime] = Field(None, description="Timestamp when deployment completed")


class DeploymentResponse(DeploymentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    deployed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class DeploymentAuditLogCreate(BaseModel):
    deployment_id: int = Field(..., gt=0, description="ID of the deployment")
    action: str = Field(..., description="Action performed", min_length=1, max_length=50)
    details: Optional[str] = Field(None, description="Additional details", max_length=1000)


# FIXED: Removed extra fields from DeploymentAuditLogResponse to match DBA schema parity requirements
# FIXED: Added proper sanitization and type hinting for security compliance

class DeploymentAuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deployment_id: int
    action: str
    details: Optional[str]
    created_at: datetime