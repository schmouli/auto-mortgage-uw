from datetime import datetime, timedelta, date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional, List, Tuple
import json

from sqlalchemy import select, func, text, and_
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.application.models import MortgageApplication
from mortgage_underwriting.modules.lender.models import LenderSubmission
from mortgage_underwriting.modules.reporting.models import ReportCache, FintracReportEntry
from mortgage_underwriting.modules.reporting.schemas import (
    PipelineMetrics, VolumeMetrics, LenderMetrics,
    ReportCacheCreate, FintracReportEntryCreate
)
from mortgage_underwriting.modules.underwriting.models import UnderwritingResult

logger = structlog.get_logger()


class ReportingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_pipeline_summary(
        self, 
        status_filter: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> PipelineMetrics:
        logger.info("pipeline_summary_requested", status_filter=status_filter)
        
        # Default to last 30 days
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
            
        # FIXED: Add date range validation
        if start_date > end_date:
            raise AppException("Invalid date range: start_date cannot be after end_date")

        # Build base query
        app_query = select(MortgageApplication)
        if status_filter:
            statuses = status_filter.split(',')
            app_query = app_query.where(MortgageApplication.status.in_(statuses))
        app_query = app_query.where(
            and_(
                MortgageApplication.created_at >= start_date,
                MortgageApplication.created_at <= end_date + timedelta(days=1)
            )
        )
        
        # Execute queries
        apps_result = await self.db.execute(app_query)
        apps = apps_result.scalars().all()
        
        # Calculate metrics
        total_active = len([a for a in apps if a.is_active])
        by_status = {}
        for app in apps:
            by_status[app.status] = by_status.get(app.status, 0) + 1
        
        # Simplified calculations (in real app would be more complex)
        avg_days_per_stage = {"submitted": Decimal("2.5"), "underwriting": Decimal("3.1")}
        approval_rate = Decimal("78.5")
        decline_reasons_frequency = {"gds_tds": 12, "credit": 8}
        
        return PipelineMetrics(
            total_active=total_active,
            by_status=by_status,
            avg_days_per_stage=avg_days_per_stage,
            approval_rate=approval_rate,
            decline_reasons_frequency=decline_reasons_frequency,
            generated_at=datetime.now(),
            period_start=start_date,
            period_end=end_date
        )

    async def get_volume_metrics(
        self, 
        period: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> VolumeMetrics:
        logger.info("volume_metrics_requested", period=period)
        
        # FIXED: Validate supported periods
        supported_periods = ["monthly", "quarterly", "ytd"]
        if period not in supported_periods:
            raise AppException(f"Unsupported period '{period}'. Must be one of: {supported_periods}")
        
        # Period handling
        if not end_date:
            end_date = date.today()
        if period == "monthly":
            if not start_date:
                start_date = end_date.replace(day=1)
        elif period == "quarterly":
            # Simplified
            start_date = date(end_date.year, ((end_date.month - 1) // 3) * 3 + 1, 1)
        elif period == "ytd":
            start_date = date(end_date.year, 1, 1)
            
        # FIXED: Add date range validation
        if start_date > end_date:
            raise AppException("Invalid date range: start_date cannot be after end_date")
        
        # Query for total volume
        vol_stmt = select(func.sum(MortgageApplication.purchase_price)).where(
            and_(
                MortgageApplication.created_at >= start_date,
                MortgageApplication.created_at <= end_date + timedelta(days=1)
            )
        )
        vol_result = await self.db.execute(vol_stmt)
        total_volume = vol_result.scalar() or Decimal("0")
        
        # Mock remaining data
        avg_deal_size = Decimal("500000") if total_volume > 0 else Decimal("0")
        applications_by_type = {"purchase": 45, "refinance": 22}
        applications_by_property = {"house": 50, "condo": 17}
        monthly_trend = {f"{end_date.year}-{end_date.month:02d}": total_volume}
        
        return VolumeMetrics(
            total_volume=total_volume,
            avg_deal_size=avg_deal_size,
            applications_by_type=applications_by_type,
            applications_by_property=applications_by_property,
            monthly_trend=monthly_trend,
            generated_at=datetime.now(),
            period_start=start_date,
            period_end=end_date
        )

    async def get_lender_metrics(
        self, 
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> LenderMetrics:
        logger.info("lender_metrics_requested")
        
        if not start_date:
            start_date = date.today().replace(day=1)
        if not end_date:
            end_date = date.today()
            
        # FIXED: Add date range validation
        if start_date > end_date:
            raise AppException("Invalid date range: start_date cannot be after end_date")
            
        # Mock data
        submissions_by_lender = {"Big Bank": 25, "Credit Union": 18}
        approval_rate_by_lender = {"Big Bank": Decimal("82.0"), "Credit Union": Decimal("76.5")}
        avg_rate_by_lender = {"Big Bank": Decimal("5.25"), "Credit Union": Decimal("5.50")}
        top_lenders = [
            {"name": "Big Bank", "volume": 25, "approval_rate": Decimal("82.0")},
            {"name": "Credit Union", "volume": 18, "approval_rate": Decimal("76.5")}
        ]
        
        return LenderMetrics(
            submissions_by_lender=submissions_by_lender,
            approval_rate_by_lender=approval_rate_by_lender,
            avg_rate_by_lender=avg_rate_by_lender,
            top_lenders=top_lenders,
            generated_at=datetime.now(),
            period_start=start_date,
            period_end=end_date
        )

    async def get_fintrac_summary(
        self, 
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> dict:  # Using dict for simplicity
        logger.info("fintrac_summary_requested")
        
        if not start_date:
            start_date = date.today().replace(day=1)
        if not end_date:
            end_date = date.today()
            
        # FIXED: Add date range validation
        if start_date > end_date:
            raise AppException("Invalid date range: start_date cannot be after end_date")
            
        # Mock data
        return {
            "total_transactions": 67,
            "high_value_transactions": 5,
            "flagged_transaction_types": {"purchase": 3, "refinance": 2},
            "report_generated_at": datetime.now(),
            "period_start": start_date,
            "period_end": end_date
        }

    async def log_report_access(
        self, 
        user_id: int, 
        report_type: str, 
        parameters: dict, 
        record_count: int, 
        file_path: Optional[str] = None
    ) -> FintracReportEntry:
        logger.info("logging_report_access", report_type=report_type, user_id=user_id)
        
        entry = FintracReportEntry(
            user_id=user_id,
            report_type=report_type,
            parameters_json=json.dumps(parameters),
            record_count=record_count,
            file_path=file_path
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry