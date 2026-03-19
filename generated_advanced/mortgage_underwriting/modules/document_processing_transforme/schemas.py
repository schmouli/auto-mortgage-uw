from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict, field_validator


class DocumentTypeEnum(str, Enum):
    T4506 = "t4506"
    NOA = "noa"
    CREDIT = "credit"
    BANK = "bank"
    PURCHASE = "purchase"


class ExtractRequest(BaseModel):
    application_id: int = Field(..., gt=0, description="FK to mortgage_applications.id")
    document_type: DocumentTypeEnum = Field(..., description="Type of document being processed")
    s3_key: str = Field(..., pattern=r"^uploads/[0-9a-f\\-]+/[^/]+\\.pdf$", description="S3 object key")
    filename: str = Field(..., max_length=255, description="Original filename for audit logging")

    @field_validator('s3_key')
    def validate_s3_key(cls, v: str) -> str:
        if not v.endswith('.pdf'):
            raise ValueError('s3_key must point to a PDF file')
        return v


class ExtractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    job_id: int = Field(..., description="ID of the extraction job")
    status: str = Field(..., description="Current status of the job")
    estimated_processing_time_seconds: Optional[int] = Field(None, description="Estimated time in seconds")
    created_at: datetime = Field(..., description="Job creation timestamp")


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    job_id: int = Field(..., description="ID of the extraction job")
    status: str = Field(..., description="Current status of the job")
    document_type: str = Field(..., description="Type of document being processed")
    confidence: Optional[Decimal] = Field(None, description="Confidence score of extraction result")
    model_version: Optional[str] = Field(None, description="Version of the model used")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp if finished")


class ExtractionResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    job_id: int = Field(..., description="ID of the extraction job")
    extracted_json: Optional[Dict[str, Any]] = Field(None, description="Structured JSON output from Donut")
    confidence: Optional[Decimal] = Field(None, description="Confidence score of extraction result")
    model_version: Optional[str] = Field(None, description="Version of the model used")
    created_at: datetime = Field(..., description="Job creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp if finished")