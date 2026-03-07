from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal, Union
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

# Request Schemas
class DPTExtractionRequest(BaseModel):
    application_id: int = Field(..., description="FK to mortgage application", gt=0)  # Changed to int and added validation
    document_type: Literal["t4_slip", "noa", "credit_report", "bank_statement", "purchase_agreement"] = Field(..., description="Type of document being processed")
    s3_key: Optional[str] = Field(None, description="S3 key if file already uploaded")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "application_id": 12345,
                "document_type": "noa",
                "s3_key": "uploads/applications/12345/noa_2023.pdf"
            }
        }
    )

# Response Schemas
class DPTExtractionResponse(BaseModel):
    job_id: UUID
    status: Literal["pending", "processing", "completed", "failed"]
    document_type: str
    created_at: datetime
    estimated_processing_time_seconds: int = Field(default=45)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "456f7890-e89b-12d3-a456-426614174001",
                "status": "pending",
                "document_type": "noa",
                "created_at": "2024-01-15T14:30:00Z",
                "estimated_processing_time_seconds": 45
            }
        }
    )

class ExtractionResultResponse(BaseModel):
    id: int
    application_id: int
    document_type: str
    s3_key: str
    extracted_json: Optional[dict]
    confidence: Optional[Decimal]
    model_version: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)