from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Optional, List

from pydantic import BaseModel, Field, ConfigDict


class ReportFilters(BaseModel):
    """Common report filtering parameters."""
    date_from: Optional[date] = Field(None, description="Start date filter (inclusive)")
    date_to: Optional[date] = Field(None, description="End date filter (inclusive)")
    lender_id: Optional[int] = Field(None, description="Filter by specific lender")


class PipelineReportQuery(ReportFilters):
    include_decline_reasons: bool = Field(True, description="Include decline reason frequency breakdown")


class VolumeReportQuery(ReportFilters):
    period: str = Field("monthly", pattern="^(monthly|quarterly|ytd)$", description="Aggregation period")


class LenderReportQuery(ReportFilters):
    pass


class PipelineSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    total_active_by_status: Dict[str, int] = Field(..., example={"draft": 15, "underwriting": 42, "approved": 128})
    avg_days_per_stage: Dict[str, Decimal] = Field(..., example={"draft": Decimal("2.5"), "underwriting": Decimal("5.8")})
    approval_rate: Decimal = Field(..., description="Approval rate percentage (0-100)", example=Decimal("78.5"))
    decline_reasons_frequency: Optional[Dict[str, int]] = Field(None, example={"gds_tds_exceeded": 12, "insufficient_income": 8})
    calculated_at: datetime = Field(..., description="Timestamp when metrics were computed")


class VolumeMetricsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    total_volume: Decimal = Field(..., description="Total mortgage volume in CAD")
    avg_deal_size: Decimal = Field(..., description="Average mortgage amount in CAD")
    applications_by_type: Dict[str, int] = Field(..., example={"purchase": 45, "refinance": 12})
    applications_by_property: Dict[str, int] = Field(..., example={"detached": 32, "condo": 25})
    monthly_trend: List[Dict[str, Decimal]] = Field(..., example=[{"month": "2024-01", "volume": Decimal("15000000")}])
    calculated_at: datetime = Field(..., description="Timestamp when metrics were computed")


class LenderPerformanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    submissions_by_lender: Dict[str, int] = Field(..., example={"Bank A": 25, "Credit Union B": 18})
    approval_rate_by_lender: Dict[str, Decimal] = Field(..., example={"Bank A": Decimal("82.5"), "Credit Union B": Decimal("76.0")})
    avg_rate_by_lender: Dict[str, Decimal] = Field(..., example={"Bank A": Decimal("5.25"), "Credit Union B": Decimal("4.95")})
    top_lenders: List[Dict[str, str | Decimal]] = Field(..., example=[{"name": "Bank A", "approval_rate": Decimal("82.5"), "avg_rate": Decimal("5.25")}])
    calculated_at: datetime = Field(..., description="Timestamp when metrics were computed")


class FintracComplianceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    report_date: datetime
    total_transactions: int
    high_value_transactions: int
    flagged_for_review: int
    compliance_status: str
    summary_notes: Optional[str]
    created_at: datetime


class ReportExportRequest(BaseModel):
    report_type: str = Field(..., pattern="^(pipeline|volume|lenders|fintrac)$")
    export_format: str = Field("csv", pattern="^(csv|json)$")
    filters: Optional[dict] = Field(None, description="Additional export filters")


class ReportExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    export_id: int
    download_url: Optional[str] = None
    status: str  # queued, processing, completed, failed
    message: Optional[str] = None