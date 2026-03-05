from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, field_validator
import re


# Request Schemas
class DeploymentCreateRequest(BaseModel):
    name: str = Field(..., max_length=100, description="Unique name for the deployment")
    description: Optional[str] = Field(None, description="Description of the deployment")
    environment: str = Field(..., pattern=r"^(development|staging|production)$", description="Environment type")
    version: str = Field(..., max_length=50, description="Version identifier")

    @field_validator('name')
    def validate_name(cls, v):
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', v):
            raise ValueError('Name must start with letter and contain only letters, numbers, hyphens and underscores')
        return v


class DeploymentUpdateRequest(BaseModel):
    description: Optional[str] = Field(None, description="Updated description")
    is_active: Optional[bool] = Field(None, description="Active status")


class ServiceCreateRequest(BaseModel):
    name: str = Field(..., max_length=100, description="Service name (e.g., backend, frontend)")
    image_tag: str = Field(..., max_length=100, description="Docker image tag")
    container_port: int = Field(..., gt=0, le=65535, description="Container port number")
    replicas: int = Field(1, ge=1, description="Number of replicas")
    cpu_limit: Decimal = Field(..., description="CPU limit in cores")
    memory_limit_mb: Decimal = Field(..., description="Memory limit in MB")
    health_check_path: Optional[str] = Field(None, max_length=200, description="Health check endpoint path")
    health_check_interval_sec: int = Field(30, ge=1, description="Health check interval in seconds")
    health_check_timeout_sec: int = Field(10, ge=1, description="Health check timeout in seconds")


class ServiceConfigurationCreateRequest(BaseModel):
    config_key: str = Field(..., max_length=100, description="Configuration key")
    config_value: str = Field(..., description="Configuration value")
    is_encrypted: bool = Field(False, description="Whether the config value should be encrypted")
    is_sensitive: bool = Field(False, description="Whether the config is sensitive")


# Response Schemas
class DeploymentResponse(BaseModel):
    model_config = {"from_attributes": True}
    
    id: int
    name: str
    description: Optional[str]
    environment: str
    version: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    changed_by: Optional[str]


class ServiceResponse(BaseModel):
    model_config = {"from_attributes": True}
    
    id: int
    deployment_id: int
    name: str
    image_tag: str
    container_port: int
    replicas: int
    cpu_limit: Decimal
    memory_limit_mb: Decimal
    health_check_path: Optional[str]
    health_check_interval_sec: int
    health_check_timeout_sec: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ServiceConfigurationResponse(BaseModel):
    model_config = {"from_attributes": True}
    
    id: int
    service_id: int
    config_key: str
    config_value: str
    is_encrypted: bool
    is_sensitive: bool
    created_at: datetime
    updated_at: datetime


class ServiceWithConfigsResponse(ServiceResponse):
    configurations: List[ServiceConfigurationResponse] = []


class DeploymentDetailResponse(DeploymentResponse):
    services: List[ServiceWithConfigsResponse] = []


class DeploymentSummaryResponse(BaseModel):
    model_config = {"from_attributes": True}
    
    id: int
    name: str
    environment: str
    version: str
    is_active: bool
    service_count: int
    last_updated: datetime