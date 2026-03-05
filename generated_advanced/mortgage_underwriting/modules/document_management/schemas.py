```python
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime
from typing import List, Optional


class DocumentCreate(BaseModel):
    client_id: int = Field(..., description="FK to clients table")
    document_type: str = Field(..., max_length=100, description="Type of document being uploaded")
    file_path: str = Field(..., max_length=500, description="Path to the stored file")
    mime_type: str = Field(..., max_length=100, description="MIME type of the uploaded file")


class DocumentUpdateStatus(BaseModel):
    status: str = Field(..., max_length=50, description="New status for the document")


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    client_id: int
    document_type: str
    file_path: str
    mime_type: str
    status: str
    created_at: datetime
    updated_at: datetime


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    document_id: int
    version_number: int
    file_path: str
    uploaded_by: int
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    skip: int
    limit: int
```