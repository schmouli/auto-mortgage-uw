from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class UiComponentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    component_type: str = Field(..., min_length=1, max_length=50)
    config_json: Optional[str] = Field(None, max_length=5000)  # JSON string
    is_active: bool = True


class UiComponentCreate(UiComponentBase):
    pass


class UiComponentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    component_type: Optional[str] = Field(None, min_length=1, max_length=50)
    config_json: Optional[str] = Field(None, max_length=5000)
    is_active: Optional[bool] = None


class UiComponentResponse(UiComponentBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: datetime


class PageComponentBase(BaseModel):
    page_id: int = Field(..., gt=0)
    component_id: int = Field(..., gt=0)
    display_order: int = Field(..., ge=0)
    config_override_json: Optional[str] = Field(None, max_length=2000)  # JSON string


class PageComponentCreate(PageComponentBase):
    pass


class PageComponentUpdate(BaseModel):
    display_order: Optional[int] = Field(None, ge=0)
    config_override_json: Optional[str] = Field(None, max_length=2000)


class PageComponentResponse(PageComponentBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    component: UiComponentResponse


class UiPageBase(BaseModel):
    route_path: str = Field(..., min_length=1, max_length=200, pattern=r"^/.+")
    page_title: str = Field(..., min_length=1, max_length=200)
    is_public: bool = False


class UiPageCreate(UiPageBase):
    components: List[PageComponentCreate] = Field(default_factory=list)


class UiPageUpdate(BaseModel):
    route_path: Optional[str] = Field(None, min_length=1, max_length=200, pattern=r"^/.+")
    page_title: Optional[str] = Field(None, min_length=1, max_length=200)
    is_public: Optional[bool] = None


class UiPageResponse(UiPageBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: datetime
    components: List[PageComponentResponse] = []