from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, UUID4
import uuid


# Input Schemas
class ExtractionRequest(BaseModel):
    application_id: UUID4 = Field(..., description="Application ID associated with this document")
    document_type: Literal["t4506", "noa", "credit", "bank", "purchase"] = Field(
        ..., description="Type of document being submitted"
    )
    s3_key: str = Field(
        ...,
        pattern=r"^documents/[a-zA-Z0-9\-_]+\.pdf$",
        description="Path to the PDF file in S3 bucket under 'documents/' prefix"
    )


# Output Schemas
class ExtractionResponse(BaseModel):
    job_id: UUID4 = Field(description="Unique job identifier")
    application_id: UUID4 = Field(description="Associated application ID")
    document_type: str = Field(description="Document type requested for processing")
    status: Literal["pending", "processing", "completed", "failed"] = Field(description="Current job status")


class JobStatusResponse(BaseModel):
    job_id: UUID4 = Field(description="Unique job identifier")
    application_id: UUID4 = Field(description="Associated application ID")
    document_type: str = Field(description="Document type requested for processing")
    status: Literal["pending", "processing", "completed", "failed"] = Field(description="Current job status")
    started_at: Optional[datetime] = Field(None, description="Timestamp when processing started")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when processing completed")


class ExtractionResultResponse(BaseModel):
    job_id: UUID4 = Field(description="Unique job identifier")
    application_id: UUID4 = Field(description="Associated application ID")
    document_type: str = Field(description="Processed document type")
    extracted_json: Dict[str, Any] = Field(description="Extracted structured data as JSON object")
    confidence: Optional[Decimal] = Field(None, description="Confidence score of extraction accuracy", ge=0, le=1)
```

```