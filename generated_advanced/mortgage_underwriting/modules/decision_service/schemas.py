from pydantic import BaseModel, Field, EmailStr
from decimal import Decimal
from datetime import datetime


class ClientBase(BaseModel):
    first_name: str = Field(..., max_length=50)
    last_name: str = Field(..., max_length=50)
    email: EmailStr = Field(...)
    phone: str | None = Field(None, max_length=20)


class ClientCreate(ClientBase):
    pass


class ClientUpdate(ClientBase):
    first_name: str | None = Field(None, max_length=50)
    last_name: str | None = Field(None, max_length=50)


class ClientResponse(ClientBase):
    model_config = {
        "from_attributes": True
    }

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime