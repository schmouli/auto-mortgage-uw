from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

# --- PIPELINE REPORT ---

class PipelinePeriod(BaseModel):
    start_date: datetime
    end_date: datetime

class ByStatusBreakdown(BaseModel):
    draft: int
    submitted: int
    underwriting: int
    approved: int
    declined: int

class AvgDaysPerStage(BaseModel):
    draft: Decimal
    submitted: Decimal
    underwriting: Decimal
    approved: Decimal
    declined: Decimal

class DeclineReasonFrequency(BaseModel):
    gds_tds_exceeded: int
    insufficient_income: int
    credit_score: int
    property_value: int

class PipelineMetrics(BaseModel):
    total_active: int
    by_status: ByStatusBreakdown
    avg_days_per_stage: AvgDaysPerStage
    approval_rate: Decimal = Field(..., ge=0, le=100)
    decline_reasons_frequency: DeclineReasonFrequency

class PipelineReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    period: PipelinePeriod
    metrics: PipelineMetrics
    generated_at: datetime

# --- VOLUME REPORT ---

class VolumeFilter(BaseModel):
    property_type: Optional[str] = None
    application_type: Optional[str] = None

class MonthlyVolumeItem(BaseModel):
    month: str  # YYYY-MM
    count: int
    total_value: Decimal
    average_deal_size: Decimal

class MortgageTypeBreakdown(BaseModel):
    purchase: int
    refinance: int
    renewal: int
    switch: int

class VolumeMetrics(BaseModel):
    total_count: int
    total_value: Decimal
    average_deal_size: Decimal
    monthly_trend: List[MonthlyVolumeItem]
    type_breakdown: MortgageTypeBreakdown

class VolumeReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    period: str  # monthly/quarterly/ytd
    filter: VolumeFilter
    metrics: VolumeMetrics
    generated_at: datetime

# --- LENDER REPORT ---

class LenderPerformanceItem(BaseModel):
    lender_id: int
    lender_name: str
    submission_count: int
    approval_rate: Decimal
    average_interest_rate: Decimal

class LenderReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: List[LenderPerformanceItem]
    generated_at: datetime

# --- FINTRAC SUMMARY ---

class FintracSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    report_month: str  # YYYY-MM
    total_transactions: int
    high_value_count: int
    sin_compliance_rate: Decimal  # Percentage
    audit_trail_complete: bool
    generated_at: datetime

# --- QUERY PARAMS ---

class PipelineQueryParams(BaseModel):
    start_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    end_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    lender_id: Optional[int] = Field(None, gt=0)

class VolumeQueryParams(BaseModel):
    period: str = Field(..., pattern='^(monthly|quarterly|ytd)$')
    property_type: Optional[str] = Field(None, pattern='^(single_family|condo|multi_unit|commercial)$')
    application_type: Optional[str] = Field(None, pattern='^(purchase|refinance|renewal|switch)$')