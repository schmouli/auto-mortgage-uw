from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional, List, Any

from sqlalchemy import select, func, text, and_, or_
from sqlalchemy.orm import selectinload
import csv
import io
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.application.models import MortgageApplication
from mortgage_underwriting.modules.client.models import Client
from mortgage_underwriting.modules.lender.models import Lender, LenderSubmission
from mortgage_underwriting.modules.reporting.models import ReportCache, FintracReportSummary, ReportExportLog
from mortgage_underwriting.modules.reporting.schemas import (
    PipelineReportQuery,
    VolumeReportQuery,
    LenderReportQuery,
    ReportExportRequest,
    PipelineSummaryResponse,
    VolumeMetricsResponse,
    LenderPerformanceResponse,
    FintracComplianceSummary
)
from mortgage_underwriting.modules.underwriting.models import UnderwritingResult
from mortgage_underwriting.modules.reporting.exceptions import ReportGenerationError, DataExportError

logger = structlog.get_logger()

class ReportingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_pipeline_summary(self, filters: PipelineReportQuery) -> PipelineSummaryResponse:
        """Generate pipeline status summary with stage durations and approval metrics."""
        try:
            logger.info("generating_pipeline_summary", filters=filters.dict())
            
            # Get application counts by status
            status_query = select(MortgageApplication.status, func.count()).group_by(MortgageApplication.status)
            status_result = await self.db.execute(status_query)
            total_active_by_status = dict(status_result.fetchall())
            
            # Calculate average days in each stage (simplified)
            now = datetime.utcnow()
            avg_days_query = select(
                MortgageApplication.status,
                func.avg(func.extract('day', now - MortgageApplication.created_at))
            ).group_by(MortgageApplication.status)
            avg_days_result = await self.db.execute(avg_days_query)
            avg_days_per_stage = {
                row[0]: Decimal(str(row[1])).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                for row in avg_days_result.fetchall()
            }
            
            # Approval rate calculation
            total_apps = sum(total_active_by_status.values())
            approved_count = total_active_by_status.get('approved', 0)
            approval_rate = (Decimal(approved_count) / Decimal(total_apps) * 100) if total_apps > 0 else Decimal('0')
            
            # Decline reasons if requested
            decline_reasons_frequency = None
            if filters.include_decline_reasons:
                decline_query = select(UnderwritingResult.decline_reasons, func.count()).where(
                    UnderwritingResult.decision == 'DECLINED'
                ).group_by(UnderwritingResult.decline_reasons)
                decline_result = await self.db.execute(decline_query)
                decline_reasons_frequency = dict(decline_result.fetchall())
            
            return PipelineSummaryResponse(
                total_active_by_status=total_active_by_status,
                avg_days_per_stage=avg_days_per_stage,
                approval_rate=approval_rate.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
                decline_reasons_frequency=decline_reasons_frequency,
                calculated_at=datetime.utcnow()
            )
        except Exception as e:
            logger.error("pipeline_summary_generation_failed", error=str(e))
            raise ReportGenerationError("Failed to generate pipeline summary")

    async def get_volume_metrics(self, filters: VolumeReportQuery) -> VolumeMetricsResponse:
        """Calculate volume metrics including trends and averages."""
        try:
            logger.info("calculating_volume_metrics", filters=filters.dict())
            
            # Total volume and count
            volume_query = select(func.sum(MortgageApplication.loan_amount), func.count())
            volume_result = await self.db.execute(volume_query)
            total_volume, app_count = volume_result.fetchone() or (Decimal('0'), 0)
            avg_deal_size = (total_volume / Decimal(app_count)) if app_count > 0 else Decimal('0')
            
            # Applications by type
            type_query = select(MortgageApplication.mortgage_type, func.count()).group_by(MortgageApplication.mortgage_type)
            type_result = await self.db.execute(type_query)
            applications_by_type = dict(type_result.fetchall())
            
            # Applications by property type
            prop_query = select(MortgageApplication.property_type, func.count()).group_by(MortgageApplication.property_type)
            prop_result = await self.db.execute(prop_query)
            applications_by_property = dict(prop_result.fetchall())
            
            # Monthly trend (last 12 months)
            twelve_months_ago = datetime.utcnow() - timedelta(days=365)
            trend_query = select(
                func.to_char(MortgageApplication.created_at, 'YYYY-MM'),
                func.sum(MortgageApplication.loan_amount)
            ).where(MortgageApplication.created_at >= twelve_months_ago).group_by(
                func.to_char(MortgageApplication.created_at, 'YYYY-MM')
            ).order_by(func.to_char(MortgageApplication.created_at, 'YYYY-MM'))
            
            trend_result = await self.db.execute(trend_query)
            monthly_trend = [
                {"month": row[0], "volume": row[1]} 
                for row in trend_result.fetchall()
            ]
            
            return VolumeMetricsResponse(
                total_volume=total_volume,
                avg_deal_size=avg_deal_size.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                applications_by_type=applications_by_type,
                applications_by_property=applications_by_property,
                monthly_trend=monthly_trend,
                calculated_at=datetime.utcnow()
            )
        except Exception as e:
            logger.error("volume_metrics_calculation_failed", error=str(e))
            raise ReportGenerationError("Failed to calculate volume metrics")

    async def get_lender_performance(self, filters: LenderReportQuery) -> LenderPerformanceResponse:
        """Breakdown lender performance metrics."""
        try:
            logger.info("analyzing_lender_performance", filters=filters.dict())
            
            # Submissions by lender
            sub_query = select(Lender.name, func.count()).select_from(
                Lender.__table__.join(LenderSubmission.__table__)
            ).group_by(Lender.name)
            sub_result = await self.db.execute(sub_query)
            submissions_by_lender = dict(sub_result.fetchall())
            
            # Approval rates by lender
            approval_query = select(
                Lender.name,
                func.count().filter(MortgageApplication.status == 'approved') / func.count() * 100
            ).select_from(
                Lender.__table__.join(LenderSubmission.__table__).join(MortgageApplication.__table__)
            ).group_by(Lender.name)
            
            approval_result = await self.db.execute(approval_query)
            approval_rate_by_lender = {
                row[0]: Decimal(str(row[1])).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
                for row in approval_result.fetchall()
            }
            
            # Average rates by lender
            rate_query = select(
                Lender.name,
                func.avg(UnderwritingResult.qualifying_rate)
            ).select_from(
                Lender.__table__.join(LenderSubmission.__table__).join(MortgageApplication.__table__).join(UnderwritingResult.__table__)
            ).group_by(Lender.name)
            
            rate_result = await self.db.execute(rate_query)
            avg_rate_by_lender = {
                row[0]: Decimal(str(row[1])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                for row in rate_result.fetchall()
            }
            
            # Top lenders table
            top_lenders = [
                {
                    "name": name,
                    "approval_rate": approval_rate_by_lender.get(name, Decimal('0')),
                    "avg_rate": avg_rate_by_lender.get(name, Decimal('0'))
                }
                for name in submissions_by_lender.keys()
            ]
            top_lenders.sort(key=lambda x: x["approval_rate"], reverse=True)
            
            return LenderPerformanceResponse(
                submissions_by_lender=submissions_by_lender,
                approval_rate_by_lender=approval_rate_by_lender,
                avg_rate_by_lender=avg_rate_by_lender,
                top_lenders=top_lenders,
                calculated_at=datetime.utcnow()
            )
        except Exception as e:
            logger.error("lender_performance_analysis_failed", error=str(e))
            raise ReportGenerationError("Failed to analyze lender performance")

    async def get_fintrac_summary(self, report_date: datetime) -> FintracComplianceSummary:
        """Get FINTRAC compliance summary for regulatory reporting."""
        try:
            logger.info("retrieving_fintrac_summary", report_date=report_date)
            
            # Query for the latest summary on or before the requested date
            stmt = select(FintracReportSummary).where(
                FintracReportSummary.report_date <= report_date
            ).order_by(FintracReportSummary.report_date.desc()).limit(1)
            
            result = await self.db.execute(stmt)
            summary = result.scalar_one_or_none()
            
            if not summary:
                raise ReportGenerationError("No FINTRAC compliance summary found for the given date")
                
            return FintracComplianceSummary.model_validate(summary)
        except Exception as e:
            logger.error("fintrac_summary_retrieval_failed", error=str(e))
            raise ReportGenerationError("Failed to retrieve FINTRAC summary")

    async def export_report_data(self, request: ReportExportRequest, user_id: int) -> Dict[str, Any]:
        """Export report data in specified format."""
        try:
            logger.info("exporting_report_data", report_type=request.report_type, export_format=request.export_format, user_id=user_id)
            
            # Log export attempt
            export_log = ReportExportLog(
                user_id=user_id,
                report_type=request.report_type,
                export_format=request.export_format,
                export_filters=request.filters,
                record_count=0,
                export_timestamp=datetime.utcnow()
            )
            
            self.db.add(export_log)
            await self.db.commit()
            
            # Generate CSV content based on report type
            if request.report_type == "pipeline":
                # Fetch pipeline data
                status_query = select(MortgageApplication.status, func.count()).group_by(MortgageApplication.status)
                status_result = await self.db.execute(status_query)
                rows = [(row[0], row[1]) for row in status_result.fetchall()]
                
                # Create CSV
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["Status", "Count"])
                writer.writerows(rows)
                
                export_log.record_count = len(rows)
                export_log.file_path = f"exports/pipeline_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                
                await self.db.commit()
                
                return {
                    "content": output.getvalue(),
                    "filename": f"pipeline_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                }
                
            elif request.report_type == "volume":
                # Fetch volume data
                volume_query = select(func.sum(MortgageApplication.loan_amount), func.count())
                volume_result = await self.db.execute(volume_query)
                total_volume, app_count = volume_result.fetchone() or (Decimal('0'), 0)
                
                # Create CSV
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["Total Volume", "Application Count"])
                writer.writerow([str(total_volume), str(app_count)])
                
                export_log.record_count = 1
                export_log.file_path = f"exports/volume_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                
                await self.db.commit()
                
                return {
                    "content": output.getvalue(),
                    "filename": f"volume_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                }
                
            elif request.report_type == "lenders":
                # Fetch lender data
                sub_query = select(Lender.name, func.count()).select_from(
                    Lender.__table__.join(LenderSubmission.__table__)
                ).group_by(Lender.name)
                sub_result = await self.db.execute(sub_query)
                rows = [(row[0], row[1]) for row in sub_result.fetchall()]
                
                # Create CSV
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["Lender", "Submissions"])
                writer.writerows(rows)
                
                export_log.record_count = len(rows)
                export_log.file_path = f"exports/lenders_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                
                await self.db.commit()
                
                return {
                    "content": output.getvalue(),
                    "filename": f"lender_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                }
                
            elif request.report_type == "fintrac":
                # Fetch FINTRAC data
                fintrac_query = select(FintracReportSummary)
                fintrac_result = await self.db.execute(fintrac_query)
                rows = [(r.report_date, r.total_transactions, r.high_value_transactions, r.flagged_for_review, r.compliance_status) 
                        for r in fintrac_result.scalars().all()]
                
                # Create CSV
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["Report Date", "Total Transactions", "High Value", "Flagged", "Compliance Status"])
                writer.writerows(rows)
                
                export_log.record_count = len(rows)
                export_log.file_path = f"exports/fintrac_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                
                await self.db.commit()
                
                return {
                    "content": output.getvalue(),
                    "filename": f"fintrac_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                }
                
            else:
                raise DataExportError(f"Unsupported report type: {request.report_type}")
                
        except Exception as e:
            logger.error("data_export_failed", error=str(e))
            # Update log with failure status
            export_log = await self.db.execute(select(ReportExportLog).order_by(ReportExportLog.id.desc()).limit(1))
            log_entry = export_log.scalar_one_or_none()
            if log_entry:
                log_entry.file_path = None
                await self.db.commit()
            raise DataExportError("Failed to export report data")