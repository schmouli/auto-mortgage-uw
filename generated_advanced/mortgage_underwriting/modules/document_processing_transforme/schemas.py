from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class DocumentType(str, Enum):
    T4 = "t4"
    NOA = "noa"
    CREDIT_REPORT = "credit_report"
    BANK_STATEMENT = "bank_statement"
    PURCHASE_AGREEMENT = "purchase_agreement"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionSubmitRequest(BaseModel):
    application_id: UUID = Field(..., description="Links to mortgage application")
    document_type: DocumentType = Field(..., description="Type of document being processed")
    s3_bucket: str = Field(..., max_length=255, description="Source bucket name")
    s3_key: str = Field(..., max_length=1024, description="PDF object key (max 10MB)")
    callback_url: Optional[HttpUrl] = Field(None, description="Webhook for completion notification")


class ExtractionSubmitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    job_id: UUID = Field(..., description="Unique extraction job identifier")
    status: JobStatus = Field(..., description="Initial status: queued")
    estimated_duration_seconds: int = Field(..., ge=0, description="Based on document type and GPU queue depth")
    submitted_at: datetime = Field(..., description="Timestamp when job was submitted")


class ExtractionStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    job_id: UUID
    status: JobStatus
    progress_percent: Optional[int] = Field(None, ge=0, le=100)
    error_message: Optional[str] = None
    last_updated: datetime


class ExtractionResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    job_id: UUID
    status: JobStatus
    document_type: DocumentType
    confidence: Optional[Decimal] = None
    model_version: Optional[str] = None
    extracted_json: Optional[dict] = None
    completed_at: Optional[datetime] = None