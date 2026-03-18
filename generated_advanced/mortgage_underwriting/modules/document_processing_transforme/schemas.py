from datetime import datetime
from decimal import Decimal
from pydantic.functional_validators import BeforeValidator
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


def validate_document_type(value: str) -> str:
    allowed_types = ["t4", "noa", "credit", "bank", "purchase"]
    if value not in allowed_types:
        raise ValueError(f"document_type must be one of: {', '.join(allowed_types)}")
    return value


class DPTExtractRequest(BaseModel):
    """Request to submit a PDF document for extraction."""
    
    application_id: UUID = Field(..., description="FK to applications table")
    document_type: str = Field(..., description="Type of document being processed")
    _validate_doc_type = BeforeValidator(validate_document_type)
    # Note: file: UploadFile handled separately in route layer


class DPTExtractResponse(BaseModel):
    """Response after submitting a PDF for extraction."""
    
    model_config = ConfigDict(from_attributes=True)
    
    job_id: UUID = Field(..., description="Unique identifier for the extraction job")
    status: Literal["pending", "processing", "completed", "failed"] = Field(..., description="Current job status")
    submitted_at: datetime = Field(..., description="Timestamp when job was submitted")
    estimated_completion_time: Optional[datetime] = Field(None, description="Estimated time of completion based on queue depth")


class DPTJobStatusResponse(BaseModel):
    """Response for polling extraction job status."""
    
    model_config = ConfigDict(from_attributes=True)
    
    job_id: UUID = Field(..., description="Unique identifier for the extraction job")
    status: Literal["pending", "processing", "completed", "failed"] = Field(..., description="Current job status")
    document_type: str = Field(..., description="Type of document being processed")
    started_at: Optional[datetime] = Field(None, description="When processing began")
    completed_at: Optional[datetime] = Field(None, description="When processing finished")
    error_message: Optional[str] = Field(None, description="Error details if job failed")


class DPTResultResponse(BaseModel):
    """Structured JSON output from successful extraction."""
    
    model_config = ConfigDict(from_attributes=True)
    
    job_id: UUID = Field(..., description="Extraction job identifier")
    extracted_json: dict = Field(..., description="Donut model's structured output")
    confidence: Optional[Decimal] = Field(None, description="Confidence score of extraction (0.0000 to 1.0000)")
    model_version: Optional[str] = Field(None, description="Version of Donut model used")
    completed_at: datetime = Field(..., description="When extraction was completed")