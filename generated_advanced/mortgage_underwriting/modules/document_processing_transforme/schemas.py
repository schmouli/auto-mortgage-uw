from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class DocumentType(str, Enum):
    t4_t4a = "t4_t4a"
    noa = "noa"
    credit_report = "credit_report"
    bank_statement = "bank_statement"
    purchase_agreement = "purchase_agreement"


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    manual_review = "manual_review"


class ExtractionSubmitRequest(BaseModel):
    application_id: str = Field(..., description="UUID of mortgage application")
    document_type: DocumentType = Field(..., description="Type of document being processed")
    s3_key: str = Field(..., description="S3 object key (format: applications/{app_id}/documents/{uuid}.pdf)")
    priority: int = Field(5, ge=1, le=10, description="Processing priority (1-10, higher = faster processing)")


class ExtractionSubmitResponse(BaseModel):
    job_id: str = Field(..., description="UUID of extraction job")
    status: JobStatus = Field(..., description="Current job status")
    estimated_processing_time_seconds: int = Field(..., description="Estimated time until completion")
    created_at: datetime = Field(..., description="Job creation timestamp")


class ExtractionStatusResponse(BaseModel):
    job_id: str = Field(..., description="UUID of extraction job")
    status: JobStatus = Field(..., description="Current job status")
    document_type: str = Field(..., description="Type of document being processed")
    confidence: Optional[Decimal] = Field(None, description="Extraction confidence score (0-1)")
    started_at: Optional[datetime] = Field(None, description="Processing start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Processing completion timestamp")
    error_code: Optional[str] = Field(None, description="Error code if job failed")
    error_detail: Optional[str] = Field(None, description="Detailed error message if job failed")


class ExtractionResultResponse(BaseModel):
    job_id: str = Field(..., description="UUID of extraction job")
    document_type: str = Field(..., description="Type of document processed")
    confidence: Decimal = Field(..., description="Extraction confidence score (0-1)")
    model_version: str = Field(..., description="Version of model used for extraction")
    extracted_json: dict = Field(..., description="Structured JSON output from extraction")
    created_at: datetime = Field(..., description="Job creation timestamp")
    completed_at: datetime = Field(..., description="Processing completion timestamp")

    model_config = ConfigDict(from_attributes=True)