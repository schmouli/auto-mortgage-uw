from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List, Any

from pydantic import BaseModel, Field, ConfigDict

class PeriodEnum(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YTD = "ytd"


class ReportRequestBase(BaseModel):
    start_date: Optional[date] = Field(None, description="Filter start date (ISO 8601)")
    end_date: Optional[date] = Field(None, description="Filter end date (ISO 8601)")


class PipelineReportRequest(ReportRequestBase):
    include_declined: bool = Field(True, description="Include declined applications in metrics")


class VolumeReportRequest(ReportRequestBase):
    period: PeriodEnum = Field(..., description="Aggregation period")


class LenderReportRequest(ReportRequestBase):
    pass


class PipelineSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    period_start: date
    period_end: date
    total_applications: int
    status_breakdown: Dict[str, int]
    avg_days_per_stage: Dict[str, Decimal]
    approval_rate: Decimal
    decline_reasons_frequency: Dict[str, int]
    gds_tds_violations: int


class VolumeMetricsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    period: PeriodEnum
    period_start: date
    period_end: date
    total_volume: Decimal
    avg_deal_size: Decimal
    applications_by_type: Dict[str, int]
    applications_by_property: Dict[str, int]
    monthly_trend: List[Dict[str, Any]]  # [{"month": "2023-01", "count": 45, "volume": 1234567.89}]


class LenderPerformanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    period_start: date
    period_end: date
    submissions_by_lender: Dict[str, int]
    approval_rates_by_lender: Dict[str, Decimal]
    avg_rates_by_lender: Dict[str, Decimal]
    top_lenders: List[Dict[str, Any]]  # [{"lender_name": "ABC Bank", "volume": 1234567.89, "approval_rate": 85.5}]


class FintracSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    period_start: date
    period_end: date
    total_transactions: int
    high_value_transactions: int
    total_value: Decimal
    flagged_reasons: Dict[str, int]
    compliance_status: str


class ReportExportFormat(str, Enum):
    CSV = "csv"
    JSON = "json"


class ReportExportRequest(ReportRequestBase):
    format: ReportExportFormat = Field(default=ReportExportFormat.CSV, description="Export format")