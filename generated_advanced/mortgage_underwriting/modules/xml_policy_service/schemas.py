from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime

class XmlPolicyDocumentCreate(BaseModel):
    """
    Schema for creating a new XML policy document.
    
    Regulatory Compliance:
    - PIPEDA: Only collects necessary fields for document management
    """
    application_id: int = Field(..., gt=0, description="FK to mortgage_applications table")
    document_name: str = Field(..., min_length=1, max_length=255)
    document_size_kb: Decimal = Field(..., gt=0, description="Size of document in kilobytes")
    content_type: str = Field(..., min_length=1, max_length=100)
    storage_path: str = Field(..., min_length=1)

class XmlPolicyDocumentUpdate(BaseModel):
    """
    Schema for updating an XML policy document.
    """
    document_name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None

class XmlPolicyDocumentResponse(BaseModel):
    """
    Response schema for XML policy document.
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    application_id: int
    document_name: str
    document_size_kb: Decimal
    content_type: str
    storage_path: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class XmlPolicyDocumentListResponse(BaseModel):
    """
    Paginated response schema for listing XML policy documents.
    """
    items: list[XmlPolicyDocumentResponse]
    total: int
    skip: int
    limit: int
```

```