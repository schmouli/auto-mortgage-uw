from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class FrontendComponentBase(BaseModel):
    name: str = Field(..., max_length=100, description="Name of the frontend component")
    component_type: str = Field(..., max_length=50, description="Type of the component (e.g., uploader, chart)")
    props: Optional[Dict[str, Any]] = Field(None, description="Props/configuration for the component")


class FrontendComponentCreate(FrontendComponentBase):
    pass


class FrontendComponentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="Name of the frontend component")
    component_type: Optional[str] = Field(None, max_length=50, description="Type of the component (e.g., uploader, chart)")
    props: Optional[Dict[str, Any]] = Field(None, description="Props/configuration for the component")
    is_active: Optional[bool] = Field(None, description="Whether the component is active")


class FrontendComponentResponse(FrontendComponentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime