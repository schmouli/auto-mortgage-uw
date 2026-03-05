```python
# --- models.py ---
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    Index,
    CheckConstraint,
)
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    changed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class Report(AuditMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("report_type IN ('pipeline', 'volume', 'lender')", name="valid_report_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)  # pipeline/volume/lender
    generated_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted JSON blob for sensitive data if needed


class MetricSnapshot(AuditMixin, Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = (
        Index('idx_metric_date', 'metric_date'),
        Index('idx_metric_type', 'metric_type'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., pipeline_summary, volume_monthly
    metric_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value_numeric: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=18, scale=2))
    value_text: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON metadata about the metric


class FintracReport(AuditMixin, Base):
    __tablename__ = "fintrac_reports"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'submitted', 'error')", name="valid_fintrac_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_transactions: Mapped[int] = mapped_column(Integer, default=0)
    flagged_count: Mapped[int] = mapped_column(Integer, default=0)
    submission_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default='pending')
    details_json: Mapped[Optional[str]] = mapped_column(Text)  # Compliance findings or errors

```

---

```python
# --- schemas.py ---
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


# Request Schemas
class ReportPeriodRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    timezone: str = Field(default="UTC", description="IANA timezone identifier")

    @validator('end_date')
    def end_date_after_start(cls, v, values, **kwargs):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('End date must be after start date')
        return v


class ExportFormatRequest(BaseModel):
    format: str = Field(default="csv", description="Export format: csv, xlsx")
    include_headers: bool = True


# Response Schemas
class PipelineStatusSummaryResponse(BaseModel):
    total_active: int
    by_status: Dict[str, int]
    avg_days_per_stage: Dict[str, float]
    approval_rate: float
    decline_reasons_frequency: Dict[str, int]


class VolumeMetricsResponse(BaseModel):
    total_volume: Decimal
    avg_deal_size: Decimal
    applications_by_type: Dict[str, int]
    applications_by_property: Dict[str, int]
    monthly_trend: List[Dict[str, Any]]


class LenderPerformanceResponse(BaseModel):
    submissions_by_lender: Dict[str, int]
    approval_rate_by_lender: Dict[str, float]
    avg_rate_by_lender: Dict[str, Decimal]


class FintracSummaryResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total_transactions: int
    flagged_count: int
    compliance_status: str
    last_submitted: Optional[datetime]

```

---

```python
# --- services.py ---
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple, Optional
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import MetricSnapshot, FintracReport
from .schemas import (
    PipelineStatusSummaryResponse,
    VolumeMetricsResponse,
    LenderPerformanceResponse,
    FintracSummaryResponse,
)
from .exceptions import ReportGenerationError


class ReportingAnalyticsService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_pipeline_status_summary(self) -> PipelineStatusSummaryResponse:
        try:
            # Simulated query results
            total_active = await self._fetch_total_active_applications()
            by_status = await self._fetch_application_counts_by_status()
            avg_days_per_stage = await self._calculate_avg_days_in_stages()
            approval_rate = await self._calculate_approval_rate()
            decline_reasons_frequency = await self._get_decline_reason_frequencies()

            return PipelineStatusSummaryResponse(
                total_active=total_active,
                by_status=by_status,
                avg_days_per_stage=avg_days_per_stage,
                approval_rate=approval_rate,
                decline_reasons_frequency=decline_reasons_frequency
            )
        except Exception as e:
            raise ReportGenerationError(f"Failed to generate pipeline summary: {str(e)}")

    async def get_volume_metrics(self, period: str) -> VolumeMetricsResponse:
        try:
            total_volume = await self._fetch_total_mortgage_volume(period)
            avg_deal_size = await self._calculate_average_deal_size(period)
            applications_by_type = await self._group_applications_by_type(period)
            applications_by_property = await self._group_applications_by_property(period)
            monthly_trend = await self._get_monthly_volume_trend(12)

            return VolumeMetricsResponse(
                total_volume=total_volume,
                avg_deal_size=avg_deal_size,
                applications_by_type=applications_by_type,
                applications_by_property=applications_by_property,
                monthly_trend=monthly_trend
            )
        except Exception as e:
            raise ReportGenerationError(f"Failed to generate volume metrics: {str(e)}")

    async def get_lender_performance(self) -> LenderPerformanceResponse:
        try:
            submissions_by_lender = await self._count_submissions_by_lender()
            approval_rate_by_lender = await self._calculate_lender_approval_rates()
            avg_rate_by_lender = await self._calculate_average_rates_by_lender()

            return LenderPerformanceResponse(
                submissions_by_lender=submissions_by_lender,
                approval_rate_by_lender=approval_rate_by_lender,
                avg_rate_by_lender=avg_rate_by_lender
            )
        except Exception as e:
            raise ReportGenerationError(f"Failed to generate lender performance report: {str(e)}")

    async def export_applications_data(self, export_format: str) -> bytes:
        try:
            # Placeholder implementation for exporting application data
            csv_content = "Application ID,Status,Lender,Amount\n1,Pending,Bank A,$300000\n"
            return csv_content.encode('utf-8')
        except Exception as e:
            raise ReportGenerationError(f"Failed to export applications data: {str(e)}")

    async def get_fintrac_summary(self) -> FintracSummaryResponse:
        try:
            stmt = select(FintracReport).order_by(FintracReport.period_end.desc()).limit(1)
            result = await self.db.execute(stmt)
            latest_report = result.scalar_one_or_none()

            if not latest_report:
                return FintracSummaryResponse(
                    period_start=datetime.min,
                    period_end=datetime.min,
                    total_transactions=0,
                    flagged_count=0,
                    compliance_status="No reports found",
                    last_submitted=None
                )

            return FintracSummaryResponse(
                period_start=latest_report.period_start,
                period_end=latest_report.period_end,
                total_transactions=latest_report.total_transactions,
                flagged_count=latest_report.flagged_count,
                compliance_status=latest_report.status,
                last_submitted=latest_report.submission_date
            )
        except Exception as e:
            raise ReportGenerationError(f"Failed to retrieve FINTRAC summary: {str(e)}")

    # Internal helper methods (simulated implementations)
    async def _fetch_total_active_applications(self) -> int:
        await asyncio.sleep(0.01)  # Simulate DB delay
        return 120

    async def _fetch_application_counts_by_status(self) -> Dict[str, int]:
        await asyncio.sleep(0.01)
        return {"Pending": 60, "Approved": 40, "Declined": 20}

    async def _calculate_avg_days_in_stages(self) -> Dict[str, float]:
        await asyncio.sleep(0.01)
        return {"Review": 3.5, "Underwriting": 5.2, "Final Approval": 1.8}

    async def _calculate_approval_rate(self) -> float:
        await asyncio.sleep(0.01)
        return round((40 / 120) * 100, 2)

    async def _get_decline_reason_frequencies(self) -> Dict[str, int]:
        await asyncio.sleep(0.01)
        return {"Credit Score": 10, "Income Verification": 7, "Property Appraisal": 3}

    async def _fetch_total_mortgage_volume(self, period: str) -> Decimal:
        await asyncio.sleep(0.01)
        return Decimal("98500000").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    async def _calculate_average_deal_size(self, period: str) -> Decimal:
        await asyncio.sleep(0.01)
        return Decimal("410000").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    async def _group_applications_by_type(self, period: str) -> Dict[str, int]:
        await asyncio.sleep(0.01)
        return {"Conventional": 180, "High-Ratio": 45, "Refinance": 30}

    async def _group_applications_by_property(self, period: str) -> Dict[str, int]:
        await asyncio.sleep(0.01)
        return {"Single Family": 200, "Townhouse": 35, "Condo": 20}

    async def _get_monthly_volume_trend(self, months_back: int) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.01)
        base_volume = Decimal("7500000")
        trend = []
        for i in range(months_back, 0, -1):
            month_date = datetime.now() - timedelta(days=i*30)
            volume = base_volume + Decimal(i*100000)
            trend.append({
                "month": month_date.strftime("%Y-%m"),
                "volume": volume.quantize(Decimal("0.01"))
            })
        return trend

    async def _count_submissions_by_lender(self) -> Dict[str, int]:
        await asyncio.sleep(0.01)
        return {
            "Bank A": 80,
            "Credit Union B": 60,
            "Mortgage Co C": 45
        }

    async def _calculate_lender_approval_rates(self) -> Dict[str, float]:
        await asyncio.sleep(0.01)
        return {
            "Bank A": 75.0,
            "Credit Union B": 80.0,
            "Mortgage Co C": 65.0
        }

    async def _calculate_average_rates_by_lender(self) -> Dict[str, Decimal]:
        await asyncio.sleep(0.01)
        return {
            "Bank A": Decimal("4.25"),
            "Credit Union B": Decimal("4.10"),
            "Mortgage Co C": Decimal("4.50")
        }
```

---

```python
# --- routes.py ---
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_async
from .services import ReportingAnalyticsService
from .schemas import (
    PipelineStatusSummaryResponse,
    VolumeMetricsResponse,
    LenderPerformanceResponse,
    FintracSummaryResponse,
    ExportFormatRequest
)

router = APIRouter(prefix="/reports", tags=["Reporting & Analytics"])

@router.get("/pipeline", response_model=PipelineStatusSummaryResponse)
async def get_pipeline_report(db: AsyncSession = Depends(get_db_async)):
    """
    Retrieve pipeline status summary including counts by status, average processing times,
    approval rate, and top decline reasons.
    
    Returns:
        PipelineStatusSummaryResponse: Summary statistics for current application pipeline.
    """
    service = ReportingAnalyticsService(db)
    return await service.get_pipeline_status_summary()


@router.get("/volume", response_model=VolumeMetricsResponse)
async def get_volume_report(
    period: str = Query(..., regex="^(monthly|quarterly|ytd)$"),
    db: AsyncSession = Depends(get_db_async)
):
    """
    Get mortgage volume metrics for specified time period.

    Args:
        period: Time aggregation level (monthly/quarterly/ytd).

    Returns:
        VolumeMetricsResponse: Aggregated volume statistics and trends.
    """
    service = ReportingAnalyticsService(db)
    return await service.get_volume_metrics(period)


@router.get("/lenders", response_model=LenderPerformanceResponse)
async def get_lender_performance_report(db: AsyncSession = Depends(get_db_async)):
    """
    Retrieve lender performance breakdown including submission volumes, approval rates,
    and average interest rates offered.

    Returns:
        LenderPerformanceResponse: Performance metrics grouped by lender.
    """
    service = ReportingAnalyticsService(db)
    return await service.get_lender_performance()


@router.get("/applications/export")
async def export_applications_report(
    export_request: ExportFormatRequest = Depends(),
    db: AsyncSession = Depends(get_db_async)
):
    """
    Export detailed applications data in requested format.

    Query Parameters:
        format: File format for export (csv/xlsx).
        include_headers: Whether to include column headers.

    Responses:
        200: Successful export with file content in body.
        400: Invalid parameters provided.
    """
    service = ReportingAnalyticsService(db)
    content = await service.export_applications_data(export_request.format)
    
    media_type = "text/csv" if export_request.format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    filename = f"applications_export.{export_request.format}"
    
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/fintrac/summary", response_model=FintracSummaryResponse)
async def get_fintrac_compliance_summary(db: AsyncSession = Depends(get_db_async)):
    """
    Retrieve latest FINTRAC compliance summary report.

    Returns:
        FintracSummaryResponse: Latest compliance status and transaction overview.
    """
    service = ReportingAnalyticsService(db)
    return await service.get_fintrac_summary()

```

---

```python
# --- exceptions.py ---
class ReportingAnalyticsBaseException(Exception):
    """Base exception class for Reporting & Analytics module."""
    pass


class ReportGenerationError(ReportingAnalyticsBaseException):
    """Raised when there is an issue generating a report."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class InvalidReportPeriodError(ReportingAnalyticsBaseException):
    """Raised when an invalid reporting period is provided."""
    def __init__(self, message: str = "Invalid reporting period specified"):
        self.message = message
        super().__init__(self.message)


class DataExportError(ReportingAnalyticsBaseException):
    """Raised when data export fails."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

```