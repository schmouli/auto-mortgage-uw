from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_validator
import json


class ComponentTypeEnum(str, Enum):
    uploader = "uploader"
    chart = "chart"
    progress_indicator = "progress_indicator"
    audit_viewer = "audit_viewer"
    exception_queue = "exception_queue"


class UIComponentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name of the UI component")
    component_type: ComponentTypeEnum = Field(..., description="Type of the UI component")
    configuration: Optional[str] = Field(None, max_length=5000, description="JSON configuration blob for the component")
    is_enabled: bool = Field(True, description="Whether the component is enabled")

    @field_validator('configuration')
    def validate_configuration(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("Configuration must be valid JSON if provided")
        return v


class UIComponentCreate(UIComponentBase):
    module_id: int = Field(..., gt=0, description="ID of the parent module")


class UIComponentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Updated name of the UI component")
    component_type: Optional[ComponentTypeEnum] = Field(None, description="Updated type of the UI component")
    configuration: Optional[str] = Field(None, max_length=5000, description="Updated JSON configuration blob")
    is_enabled: Optional[bool] = Field(None, description="Updated enabled status")

    @field_validator('configuration')
    def validate_configuration(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("Configuration must be valid JSON if provided")
        return v


class UIComponentResponse(UIComponentBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    module_id: int
    created_at: datetime
    updated_at: datetime


class FrontendUIModuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Unique name of the UI module")
    description: Optional[str] = Field(None, max_length=500, description="Description of the module's purpose")
    is_active: bool = Field(True, description="Whether the module is active")


class FrontendUIModuleCreate(FrontendUIModuleBase):
    pass


class FrontendUIModuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Updated name of the UI module")
    description: Optional[str] = Field(None, max_length=500, description="Updated description of the module")
    is_active: Optional[bool] = Field(None, description="Updated active status")


class FrontendUIModuleResponse(FrontendUIModuleBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    ui_components: List[UIComponentResponse] = []
    created_at: datetime
    updated_at: datetime