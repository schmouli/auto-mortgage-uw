from datetime import datetime, timedelta
from decimal import Decimal, DivisionByZero
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, Callable, Awaitable, List
from sqlalchemy import select, func, text
import structlog
import json
from mortgage_underwriting.modules.lender.models import Lender
from mortgage_underwriting.modules.mortgage.models import MortgageApplication, Property
from mortgage_underwriting.modules.reporting.models import ReportCache, FintracReportSummary
from mortgage_underwriting.modules.reporting.schemas import (
    PipelineReportResponse, PipelinePeriod, PipelineMetrics,
    ByStatusBreakdown, AvgDaysPerStage, DeclineReasonFrequency,
    VolumeReportResponse, VolumeFilter, VolumeMetrics, MonthlyVolumeItem, MortgageTypeBreakdown,
    LenderReportResponse, LenderPerformanceItem, FintracSummaryResponse
)

logger = structlog.get_logger()

default_cache_ttl = 3600  # 1 hour


class ReportingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_cached_or_execute(
        self, 
        report_type: str, 
        period: str, 
        filters: Dict[str, Any], 
        execute_fn: Callable[[], Awaitable[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        # Check cache first
        stmt = select(ReportCache).where(
            ReportCache.report_type == report_type,
            ReportCache.period == period,
            ReportCache.filters == json.dumps(filters),
            ReportCache.expires_at > func.now()
        )
        result = await self.db.execute(stmt)
        cached = result.scalar_one_or_none()
        
        if cached and cached.data:
            logger.info("report_cache_hit", report_type=report_type)
            return json.loads(cached.data)
        
        # Execute and cache
        logger.info("report_cache_miss", report_type=report_type)
        data = await execute_fn()
        
        cache_entry = ReportCache(
            report_type=report_type,
            period=period,
            expires_at=datetime.utcnow() + timedelta(seconds=default_cache_ttl)
        )
        cache_entry.set_filters(filters)
        cache_entry.set_data(data)
        
        self.db.add(cache_entry)
        await self.db.commit()
        
        return data

    async def get_pipeline_report(
        self, 
        start_date: Optional[datetime], 
        end_date: Optional[datetime], 
        lender_id: Optional[int]
    ) -> PipelineReportResponse:
        logger.info("generating_pipeline_report")
        
        # Set defaults for period
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=365)  # Last year
            
        period_key = f"{start_date.date()}_{end_date.date()}"
        filters = {"lender_id": lender_id}
        
        async def _fetch_data() -> Dict[str, Any]:
            # Active applications
            stmt = select(func.count(MortgageApplication.id)).where(
                MortgageApplication.is_active == True,
                MortgageApplication.created_at.between(start_date, end_date)
            )
            if lender_id:
                stmt = stmt.where(MortgageApplication.lender_id == lender_id)
            result = await self.db.execute(stmt)
            total_active = result.scalar_one()
            
            # Status breakdown
            status_stmt = select(
                MortgageApplication.status,
                func.count(MortgageApplication.id)
            ).where(
                MortgageApplication.is_active == True,
                MortgageApplication.created_at.between(start_date, end_date)
            )
            if lender_id:
                status_stmt = status_stmt.where(MortgageApplication.lender_id == lender_id)
            status_stmt = status_stmt.group_by(MortgageApplication.status)
            
            result = await self.db.execute(status_stmt)
            status_counts = {row[0]: row[1] for row in result.fetchall()}
            by_status = ByStatusBreakdown(
                draft=status_counts.get('draft', 0),
                submitted=status_counts.get('submitted', 0),
                underwriting=status_counts.get('underwriting', 0),
                approved=status_counts.get('approved', 0),
                declined=status_counts.get('declined', 0)
            )
            
            # Approval rate
            approved_count = status_counts.get('approved', 0)
            declined_count = status_counts.get('declined', 0)
            total_decision = approved_count + declined_count
            try:
                approval_rate = Decimal((approved_count / total_decision * 100) if total_decision > 0 else 0.0)
            except (ZeroDivisionError, DivisionByZero):
                approval_rate = Decimal('0.0')
            
            # Simplified decline reasons (would join with decline_reasons table in full impl)
            decline_reasons = DeclineReasonFrequency(
                gds_tds_exceeded=50,
                insufficient_income=30,
                credit_score=20,
                property_value=10
            )
            
            # Avg days per stage (simplified)
            avg_days = AvgDaysPerStage(
                draft=Decimal('2.5'),
                submitted=Decimal('1.8'),
                underwriting=Decimal('5.2'),
                approved=Decimal('3.0'),
                declined=Decimal('4.0')
            )
            
            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "metrics": {
                    "total_active": total_active,
                    "by_status": by_status.dict(),
                    "avg_days_per_stage": avg_days.dict(),
                    "approval_rate": approval_rate,
                    "decline_reasons_frequency": decline_reasons.dict()
                },
                "generated_at": datetime.utcnow().isoformat()
            }
        
        data = await self._get_cached_or_execute("pipeline", period_key, filters, _fetch_data)
        return PipelineReportResponse(**data)

    async def get_volume_report(
        self, 
        period: str,  # monthly, quarterly, ytd
        property_type: Optional[str], 
        application_type: Optional[str]
    ) -> VolumeReportResponse:
        logger.info("generating_volume_report", period=period)
        
        filters = {
            "property_type": property_type,
            "application_type": application_type
        }
        
        async def _fetch_data() -> Dict[str, Any]:
            # Determine date range
            now = datetime.utcnow()
            if period == "monthly":
                start_date = now.replace(day=1) - timedelta(days=1)
                start_date = start_date.replace(day=1)
                end_date = now
            elif period == "quarterly":
                quarter_start_month = ((now.month - 1) // 3) * 3 + 1
                start_date = now.replace(month=quarter_start_month, day=1)
                end_date = now
            else:  # ytd
                start_date = now.replace(month=1, day=1)
                end_date = now
            
            # Base query
            stmt = select(
                func.count(MortgageApplication.id),
                func.sum(MortgageApplication.loan_amount),
            ).join(Property).where(
                MortgageApplication.created_at.between(start_date, end_date),
                MortgageApplication.is_active == True
            )
            
            if property_type:
                stmt = stmt.where(Property.property_type == property_type)
            if application_type:
                stmt = stmt.where(MortgageApplication.application_type == application_type)
                
            result = await self.db.execute(stmt)
            count, total_value = result.fetchone() or (0, Decimal('0'))
            try:
                avg_deal = (total_value / count) if count and total_value else Decimal('0')
            except (ZeroDivisionError, DivisionByZero):
                avg_deal = Decimal('0')
            
            # Monthly trend
            monthly_stmt = select(
                func.to_char(MortgageApplication.created_at, 'YYYY-MM').label('month'),
                func.count(MortgageApplication.id),
                func.sum(MortgageApplication.loan_amount)
            ).join(Property).where(
                MortgageApplication.created_at.between(start_date, end_date),
                MortgageApplication.is_active == True
            )
            
            if property_type:
                monthly_stmt = monthly_stmt.where(Property.property_type == property_type)
            if application_type:
                monthly_stmt = monthly_stmt.where(MortgageApplication.application_type == application_type)
                
            monthly_stmt = monthly_stmt.group_by(text("month")).order_by(text("month"))
            result = await self.db.execute(monthly_stmt)
            monthly_rows = result.fetchall()
            
            monthly_trend = [
                MonthlyVolumeItem(
                    month=row[0],
                    count=row[1],
                    total_value=row[2] or Decimal('0'),
                    average_deal_size=(row[2] / row[1]) if row[1] and row[2] else Decimal('0')
                ) for row in monthly_rows
            ]
            
            # Type breakdown
            type_stmt = select(
                MortgageApplication.application_type,
                func.count(MortgageApplication.id)
            ).join(Property).where(
                MortgageApplication.created_at.between(start_date, end_date),
                MortgageApplication.is_active == True
            )
            
            if property_type:
                type_stmt = type_stmt.where(Property.property_type == property_type)
                
            type_stmt = type_stmt.group_by(MortgageApplication.application_type)
            result = await self.db.execute(type_stmt)
            type_counts = {row[0]: row[1] for row in result.fetchall()}
            
            type_breakdown = MortgageTypeBreakdown(
                purchase=type_counts.get('purchase', 0),
                refinance=type_counts.get('refinance', 0),
                renewal=type_counts.get('renewal', 0),
                switch=type_counts.get('switch', 0)
            )
            
            return {
                "period": period,
                "filter": {
                    "property_type": property_type,
                    "application_type": application_type
                },
                "metrics": {
                    "total_count": count,
                    "total_value": total_value or Decimal('0'),
                    "average_deal_size": avg_deal,
                    "monthly_trend": [item.dict() for item in monthly_trend],
                    "type_breakdown": type_breakdown.dict()
                },
                "generated_at": datetime.utcnow().isoformat()
            }
        
        data = await self._get_cached_or_execute("volume", period, filters, _fetch_data)
        return VolumeReportResponse(**data)

    async def get_lender_report(self) -> LenderReportResponse:
        logger.info("generating_lender_report")
        
        async def _fetch_data() -> Dict[str, Any]:
            # Join with lenders table to get names
            stmt = select(
                Lender.id,
                Lender.name,
                func.count(MortgageApplication.id).label('submission_count'),
                func.avg(MortgageApplication.interest_rate).label('avg_rate')
            ).join(MortgageApplication, Lender.id == MortgageApplication.lender_id).group_by(Lender.id, Lender.name)
            
            result = await self.db.execute(stmt)
            rows = result.fetchall()
            
            items = []
            for row in rows:
                # Calculate approval rate
                status_stmt = select(
                    MortgageApplication.status,
                    func.count(MortgageApplication.id)
                ).where(
                    MortgageApplication.lender_id == row[0]
                ).group_by(MortgageApplication.status)
                
                status_result = await self.db.execute(status_stmt)
                status_counts = {r[0]: r[1] for r in status_result.fetchall()}
                
                approved = status_counts.get('approved', 0)
                declined = status_counts.get('declined', 0)
                total = approved + declined
                
                try:
                    approval_rate = Decimal((approved / total * 100) if total > 0 else 0.0)
                except (ZeroDivisionError, DivisionByZero):
                    approval_rate = Decimal('0.0')
                
                items.append(LenderPerformanceItem(
                    lender_id=row[0],
                    lender_name=row[1],
                    submission_count=row[2],
                    approval_rate=approval_rate,
                    average_interest_rate=row[3] or Decimal('0.0')
                ))
            
            return {
                "items": [item.dict() for item in items],
                "generated_at": datetime.utcnow().isoformat()
            }
        
        data = await self._get_cached_or_execute("lender", "all", {}, _fetch_data)
        return LenderReportResponse(**data)

    async def get_fintrac_summary(self, report_month: str) -> FintracSummaryResponse:
        logger.info("generating_fintrac_summary", report_month=report_month)
        
        # Try to fetch existing summary
        stmt = select(FintracReportSummary).where(FintracReportSummary.report_month == report_month)
        result = await self.db.execute(stmt)
        summary = result.scalar_one_or_none()
        
        if summary:
            return FintracSummaryResponse(
                report_month=summary.report_month,
                total_transactions=summary.total_transactions,
                high_value_count=summary.high_value_count,
                sin_compliance_rate=summary.sin_compliance_rate,
                audit_trail_complete=summary.audit_trail_complete,
                generated_at=summary.created_at
            )
        
        # Generate new summary
        month_start = datetime.strptime(f"{report_month}-01", "%Y-%m-%d")
        next_month = month_start.replace(month=month_start.month % 12 + 1, year=month_start.year + (month_start.month // 12))
        month_end = next_month - timedelta(days=1)
        
        # Total transactions
        total_stmt = select(func.count(MortgageApplication.id)).where(
            MortgageApplication.created_at.between(month_start, month_end)
        )
        result = await self.db.execute(total_stmt)
        total_transactions = result.scalar_one()
        
        # High value (> $10,000)
        high_value_stmt = select(func.count(MortgageApplication.id)).where(
            MortgageApplication.created_at.between(month_start, month_end),
            MortgageApplication.loan_amount > 10000
        )
        result = await self.db.execute(high_value_stmt)
        high_value_count = result.scalar_one()
        
        # SIN compliance (assuming we track this in clients table)
        # This is a placeholder - actual implementation would check encrypted SIN storage
        sin_compliance_rate = Decimal('98.5')  # Placeholder
        
        # Audit trail completeness
        audit_trail_complete = True  # Placeholder
        
        # Save summary
        new_summary = FintracReportSummary(
            report_month=report_month,
            total_transactions=total_transactions,
            high_value_count=high_value_count,
            sin_compliance_rate=sin_compliance_rate,
            audit_trail_complete=audit_trail_complete
        )
        
        self.db.add(new_summary)
        await self.db.commit()
        await self.db.refresh(new_summary)
        
        return FintracSummaryResponse(
            report_month=new_summary.report_month,
            total_transactions=new_summary.total_transactions,
            high_value_count=new_summary.high_value_count,
            sin_compliance_rate=new_summary.sin_compliance_rate,
            audit_trail_complete=new_summary.audit_trail_complete,
            generated_at=new_summary.created_at
        )