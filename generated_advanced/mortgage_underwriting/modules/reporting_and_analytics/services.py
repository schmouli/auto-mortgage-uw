from datetime import datetime, timedelta, date
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Tuple, Any, Optional, Union, IO
import json
import csv
import io

from sqlalchemy import select, func, text, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.application.models import MortgageApplication, ApplicationStatus
from mortgage_underwriting.modules.client.models import Client
from mortgage_underwriting.modules.lending.models import LenderOffer

from .models import ReportCache, FintracReport
from .schemas import (
    PipelineReportRequest,
    VolumeReportRequest,
    LenderReportRequest,
    PipelineSummaryResponse,
    VolumeMetricsResponse,
    LenderPerformanceResponse,
    FintracSummaryResponse,
    PeriodEnum
)

logger = structlog.get_logger()

class ReportingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_pipeline_summary(self, request: PipelineReportRequest) -> PipelineSummaryResponse:
        """Calculate pipeline metrics including status breakdown, average processing times, and GDS/TDS violations."""
        logger.info("reporting.pipeline_summary_requested", start_date=request.start_date, end_date=request.end_date)
        
        # Build base query
        query = select(MortgageApplication)
        if request.start_date:
            query = query.where(MortgageApplication.created_at >= request.start_date)
        if request.end_date:
            query = query.where(MortgageApplication.created_at <= request.end_date + timedelta(days=1))
        if not request.include_declined:
            query = query.where(MortgageApplication.status != ApplicationStatus.DECLINED)
            
        # Execute query with relationships
        result = await self.db.execute(query.options(selectinload(MortgageApplication.offers)))
        applications = result.scalars().all()
        
        # Calculate metrics
        total_count = len(applications)
        status_counts: Dict[str, int] = {}
        stage_durations: Dict[str, List[float]] = {}
        decline_reasons: Dict[str, int] = {}
        gds_tds_violations = 0
        
        for app in applications:
            # Status breakdown
            status = app.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Stage duration tracking
            stages = ['submitted', 'underwriting', 'approved', 'funded']
            current_stage_index = stages.index(status) if status in stages else 0
            for i in range(current_stage_index + 1):
                stage = stages[i]
                if stage not in stage_durations:
                    stage_durations[stage] = []
                # In real implementation, would calculate actual time differences
                stage_durations[stage].append(float(i + 1))
                
            # Decline reasons
            if app.status == ApplicationStatus.DECLINED and app.decline_reason:
                reason = app.decline_reason
                decline_reasons[reason] = decline_reasons.get(reason, 0) + 1
                
            # GDS/TDS violations check
            if hasattr(app, 'gds_ratio') and hasattr(app, 'tds_ratio'):
                if app.gds_ratio > Decimal('0.39') or app.tds_ratio > Decimal('0.44'):
                    gds_tds_violations += 1
        
        # Average days per stage
        avg_days_per_stage: Dict[str, Decimal] = {}
        for stage, durations in stage_durations.items():
            avg_days_per_stage[stage] = Decimal(sum(durations) / len(durations)).quantize(Decimal('0.1')) if durations else Decimal('0')
        
        # Approval rate
        approved_count = status_counts.get(ApplicationStatus.APPROVED.value, 0)
        approval_rate = (Decimal(approved_count) / Decimal(total_count) * 100).quantize(Decimal('0.1')) if total_count > 0 else Decimal('0')
        
        response = PipelineSummaryResponse(
            period_start=request.start_date or datetime.min.date(),
            period_end=request.end_date or datetime.now().date(),
            total_applications=total_count,
            status_breakdown=status_counts,
            avg_days_per_stage=avg_days_per_stage,
            approval_rate=approval_rate,
            decline_reasons_frequency=decline_reasons,
            gds_tds_violations=gds_tds_violations
        )
        
        logger.info("reporting.pipeline_summary_generated", total_applications=total_count)
        return response

    async def get_volume_metrics(self, request: VolumeReportRequest) -> VolumeMetricsResponse:
        """Aggregate mortgage volume statistics by period."""
        logger.info("reporting.volume_metrics_requested", period=request.period.value)
        
        # This is a simplified version - in practice would group by actual periods
        today = datetime.now().date()
        if request.period == PeriodEnum.MONTHLY:
            period_start = today.replace(day=1)
            period_end = today
        elif request.period == PeriodEnum.QUARTERLY:
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            period_start = today.replace(month=quarter_start_month, day=1)
            period_end = today
        else:  # YTD
            period_start = today.replace(month=1, day=1)
            period_end = today
            
        # Query applications in period
        query = select(MortgageApplication)
        if request.start_date:
            query = query.where(MortgageApplication.created_at >= request.start_date)
        if request.end_date:
            query = query.where(MortgageApplication.created_at <= request.end_date + timedelta(days=1))
            
        result = await self.db.execute(query)
        applications = result.scalars().all()
        
        # Aggregate metrics
        total_volume = sum(app.purchase_price for app in applications)
        avg_deal_size = total_volume / len(applications) if applications else Decimal('0')
        
        # Group by type/property (placeholder logic)
        apps_by_type: Dict[str, int] = {}
        apps_by_property: Dict[str, int] = {}
        for app in applications:
            app_type = getattr(app, 'application_type', 'unknown') or 'unknown'
            property_type = getattr(app.property, 'property_type', 'unknown') if hasattr(app, 'property') else 'unknown'
            apps_by_type[app_type] = apps_by_type.get(app_type, 0) + 1
            apps_by_property[property_type] = apps_by_property.get(property_type, 0) + 1
            
        # Monthly trend (last 12 months placeholder)
        monthly_trend = [
            {"month": f"{today.year}-{i:02d}", "count": 0, "volume": Decimal('0')} 
            for i in range(1, 13)
        ]
        
        response = VolumeMetricsResponse(
            period=request.period,
            period_start=period_start,
            period_end=period_end,
            total_volume=total_volume,
            avg_deal_size=avg_deal_size,
            applications_by_type=apps_by_type,
            applications_by_property=apps_by_property,
            monthly_trend=monthly_trend
        )
        
        logger.info("reporting.volume_metrics_generated", total_volume=float(total_volume))
        return response

    async def get_lender_performance(self, request: LenderReportRequest) -> LenderPerformanceResponse:
        """Analyze lender submission rates, approvals, and average rates."""
        logger.info("reporting.lender_performance_requested")
        
        # Join applications with offers to get lender info
        query = select(MortgageApplication, LenderOffer).join(LenderOffer)
        if request.start_date:
            query = query.where(MortgageApplication.created_at >= request.start_date)
        if request.end_date:
            query = query.where(MortgageApplication.created_at <= request.end_date + timedelta(days=1))
            
        result = await self.db.execute(query)
        rows = result.all()
        
        # Group by lender
        lender_stats: Dict[str, Dict[str, Any]] = {}
        for app, offer in rows:
            lender_name = offer.lender.name if offer.lender else 'Unknown'
            if lender_name not in lender_stats:
                lender_stats[lender_name] = {
                    'submissions': 0,
                    'approvals': 0,
                    'rates': []
                }
            lender_stats[lender_name]['submissions'] += 1
            if app.status == ApplicationStatus.APPROVED:
                lender_stats[lender_name]['approvals'] += 1
            if offer.interest_rate:
                lender_stats[lender_name]['rates'].append(float(offer.interest_rate))
        
        # Calculate metrics
        submissions_by_lender = {name: stats['submissions'] for name, stats in lender_stats.items()}
        approval_rates_by_lender = {}
        avg_rates_by_lender = {}
        
        for name, stats in lender_stats.items():
            approval_rate = (stats['approvals'] / stats['submissions'] * 100) if stats['submissions'] > 0 else 0
            approval_rates_by_lender[name] = Decimal(approval_rate).quantize(Decimal('0.1'))
            avg_rate = sum(stats['rates']) / len(stats['rates']) if stats['rates'] else 0
            avg_rates_by_lender[name] = Decimal(avg_rate).quantize(Decimal('0.01'))
        
        # Top lenders by volume
        top_lenders = sorted([
            {
                'lender_name': name,
                'volume': Decimal(stats['submissions'] * 100000),  # Placeholder value
                'approval_rate': approval_rates_by_lender[name]
            }
            for name, stats in lender_stats.items()
        ], key=lambda x: x['volume'], reverse=True)[:10]
        
        response = LenderPerformanceResponse(
            period_start=request.start_date or datetime.min.date(),
            period_end=request.end_date or datetime.now().date(),
            submissions_by_lender=submissions_by_lender,
            approval_rates_by_lender=approval_rates_by_lender,
            avg_rates_by_lender=avg_rates_by_lender,
            top_lenders=top_lenders
        )
        
        logger.info("reporting.lender_performance_generated", lenders_count=len(lender_stats))
        return response

    async def get_fintrac_summary(self, request: LenderReportRequest) -> FintracSummaryResponse:
        """Generate FINTRAC compliance summary for high-value transactions."""
        logger.info("reporting.fintrac_summary_requested")
        
        # Query FintracReports
        query = select(FintracReport)
        if request.start_date:
            query = query.where(FintracReport.created_at >= request.start_date)
        if request.end_date:
            query = query.where(FintracReport.created_at <= request.end_date + timedelta(days=1))
            
        result = await self.db.execute(query)
        reports = result.scalars().all()
        
        # Aggregate metrics
        total_transactions = len(reports)
        high_value_count = sum(1 for r in reports if r.is_high_value)
        total_value = sum(r.transaction_amount for r in reports)
        
        # Flagged reasons
        flagged_reasons: Dict[str, int] = {}
        for report in reports:
            if report.flagged_reason:
                reason = report.flagged_reason
                flagged_reasons[reason] = flagged_reasons.get(reason, 0) + 1
        
        # Compliance status (simplified)
        compliance_status = 'compliant' if all(r.reported_at for r in reports) else 'pending'
        
        response = FintracSummaryResponse(
            period_start=request.start_date or datetime.min.date(),
            period_end=request.end_date or datetime.now().date(),
            total_transactions=total_transactions,
            high_value_transactions=high_value_count,
            total_value=total_value,
            flagged_reasons=flagged_reasons,
            compliance_status=compliance_status
        )
        
        logger.info("reporting.fintrac_summary_generated", total_transactions=total_transactions)
        return response

    async def export_applications(self, request: ReportExportRequest) -> str:
        """Export applications data as CSV."""
        logger.info("reporting.applications_export_requested", format=request.format.value)
        
        # Query applications
        query = select(MortgageApplication)
        if request.start_date:
            query = query.where(MortgageApplication.created_at >= request.start_date)
        if request.end_date:
            query = query.where(MortgageApplication.created_at <= request.end_date + timedelta(days=1))
            
        result = await self.db.execute(query)
        applications = result.scalars().all()
        
        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Client ID', 'Purchase Price', 'Status', 'Created At'])
        for app in applications:
            writer.writerow([
                app.id,
                app.client_id,
                float(app.purchase_price),
                app.status.value,
                app.created_at.isoformat()
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        logger.info("reporting.applications_export_generated", row_count=len(applications))
        return csv_content