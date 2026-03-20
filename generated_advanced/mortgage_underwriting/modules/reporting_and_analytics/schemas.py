from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Optional, List, Union

from pydantic import BaseModel, Field, ConfigDict


class PipelineMetrics(BaseModel):
    total_active: int = Field(..., ge=0)
    by_status: Dict[str, int]
    avg_days_per_stage: Dict[str, Decimal]
    approval_rate: Decimal = Field(..., ge=0, le=100)
    decline_reasons_frequency: Dict[str, int]
    generated_at: datetime
    period_start: date
    period_end: date


class VolumeMetrics(BaseModel):
    total_volume: Decimal = Field(..., ge=0)
    avg_deal_size: Decimal = Field(..., ge=0)
    applications_by_type: Dict[str, int]
    applications_by_property: Dict[str, int]
    monthly_trend: Dict[str, Decimal]  # key: YYYY-MM
    generated_at: datetime
    period_start: date
    period_end: date


class LenderMetrics(BaseModel):
    submissions_by_lender: Dict[str, int]  # lender_name: count
    approval_rate_by_lender: Dict[str, Decimal]  # lender_name: rate
    avg_rate_by_lender: Dict[str, Decimal]  # lender_name: rate
    top_lenders: List[Dict[str, Union[str, int, Decimal]]]  # [{name, volume, approval_rate}, ...]
    generated_at: datetime
    period_start: date
    period_end: date


class ReportQueryParams(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class PipelineQueryParams(ReportQueryParams):
    status_filter: Optional[str] = Field(None, description="Comma-separated statuses")


class VolumeQueryParams(ReportQueryParams):
    period: str = Field(..., pattern="^(monthly|quarterly|ytd)$")


class FintracSummaryResponse(BaseModel):
    total_transactions: int = Field(..., ge=0)
    high_value_transactions: int = Field(..., ge=0, description=">CAD $10,000")
    flagged_transaction_types: Dict[str, int]
    report_generated_at: datetime
    period_start: date
    period_end: date


class ReportExportResponse(BaseModel):
    download_url: str = Field(..., description="Temporary signed URL for CSV download")
    expires_at: datetime


# --- Internal/DB schemas ---


class ReportCacheCreate(BaseModel):
    report_type: str
    period_start: datetime
    period_end: datetime
    data_json: str
    expires_at: datetime


class ReportCacheResponse(ReportCacheCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    generated_at: datetime
    created_at: datetime
    updated_at: datetime


class FintracReportEntryCreate(BaseModel):
    user_id: int
    report_type: str
    parameters_json: str
    record_count: int
    file_path: Optional[str] = None


class FintracReportEntryResponse(FintracReportEntryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    generated_at: datetime
    created_at: datetime