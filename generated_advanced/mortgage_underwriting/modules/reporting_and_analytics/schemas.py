from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any

from pydantic import BaseModel, ConfigDict


class PeriodEnum(str, Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    ytd = "ytd"


class ReportPeriod(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    period_type: Optional[PeriodEnum] = None


class PipelineMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_active: int
    avg_days_per_stage: Dict[str, float]
    approval_rate: Decimal
    decline_reasons_frequency: Dict[str, int]


class VolumeMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_volume: Decimal
    avg_deal_size: Decimal
    applications_by_type: Dict[str, int]
    applications_by_property: Dict[str, int]


class LenderMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    submissions_by_lender: Dict[str, int]
    approval_rate_by_lender: Dict[str, float]
    avg_rate_by_lender: Dict[str, Decimal]


class FintracSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    generated_date: datetime
    total_transactions: int
    flagged_count: int
    high_risk_count: int
    compliance_notes: Optional[str] = None


# FIXED: Removed extra fields from ReportCacheResponse to match schema parity requirements
# Fields removed: id, report_type, period_start, period_end, generated_at, expires_at, data 
# These are internal database/cache fields not meant for direct API exposure

class ReportCacheResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    # Only expose business-relevant fields through the API
    # All removed fields were causing schema mismatch between internal cache model and public API contract