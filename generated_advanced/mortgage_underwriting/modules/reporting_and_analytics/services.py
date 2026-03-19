from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional

from sqlalchemy import select, func, and_
import csv
import io
import structlog

from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.application.models import Application
from mortgage_underwriting.modules.lender.models import LenderSubmission
from mortgage_underwriting.modules.reporting.models import FintracReportSummary, ReportCache
from mortgage_underwriting.modules.reporting.schemas import PipelineMetrics, VolumeMetrics, LenderMetrics, PeriodEnum, FintracSummaryResponse
from mortgage_underwriting.modules.underwriting.models import UnderwritingResult

logger = structlog.get_logger()

class ReportingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_pipeline_metrics(self) -> PipelineMetrics:
        logger.info("fetching_pipeline_metrics")
        try:
            # Total Active Applications
            total_active_query = select(func.count(Application.id)).where(Application.status == 'active')
            total_active_result = await self.db.execute(total_active_query)
            total_active = total_active_result.scalar() or 0

            # Average Days Per Stage (mock example)
            avg_days_per_stage: Dict[str, float] = {
                "submitted": 2.5,
                "under_review": 4.0,
                "approved": 1.2
            }

            # Approval Rate
            approved_query = select(func.count(UnderwritingResult.id)).where(UnderwritingResult.qualifies.is_(True))
            total_query = select(func.count(UnderwritingResult.id))
            approved_result = await self.db.execute(approved_query)
            total_result = await self.db.execute(total_query)
            approved_count = approved_result.scalar() or 0
            total_count = total_result.scalar() or 1
            approval_rate = Decimal(str(round(float(approved_count) / total_count, 4))) if total_count > 0 else Decimal('0.0000')

            # Decline Reasons Frequency (mock example)
            decline_reasons_frequency: Dict[str, int] = {
                "credit_score": 15,
                "income_verification": 8,
                "debt_to_income": 12
            }

            return PipelineMetrics(
                total_active=total_active,
                avg_days_per_stage=avg_days_per_stage,
                approval_rate=approval_rate,
                decline_reasons_frequency=decline_reasons_frequency
            )
        except Exception as e:
            logger.error("pipeline_metrics_error", exc_info=e)
            raise AppException("Failed to fetch pipeline metrics") from e

    async def get_volume_metrics(self, period: PeriodEnum) -> VolumeMetrics:
        logger.info("fetching_volume_metrics", period=period.value)
        try:
            now = datetime.utcnow()
            if period == PeriodEnum.monthly:
                start_date = now.replace(day=1)
            elif period == PeriodEnum.quarterly:
                quarter = (now.month - 1) // 3 + 1
                start_month = ((quarter - 1) * 3) + 1
                start_date = now.replace(month=start_month, day=1)
            else:  # YTD
                start_date = now.replace(month=1, day=1)

            # Total Volume
            volume_query = select(func.sum(Application.loan_amount)).where(Application.created_at >= start_date)
            volume_result = await self.db.execute(volume_query)
            total_volume = volume_result.scalar() or Decimal('0.00')

            # Avg Deal Size
            count_query = select(func.count(Application.id)).where(Application.created_at >= start_date)
            count_result = await self.db.execute(count_query)
            app_count = count_result.scalar() or 1
            avg_deal_size = total_volume / Decimal(app_count) if app_count > 0 else Decimal('0.00')

            # Applications by Type and Property (mock examples)
            applications_by_type: Dict[str, int] = {
                "purchase": 45,
                "refinance": 20
            }
            applications_by_property: Dict[str, int] = {
                "single_family": 50,
                "condo": 15
            }

            return VolumeMetrics(
                total_volume=total_volume,
                avg_deal_size=avg_deal_size,
                applications_by_type=applications_by_type,
                applications_by_property=applications_by_property
            )
        except Exception as e:
            logger.error("volume_metrics_error", exc_info=e)
            raise AppException("Failed to fetch volume metrics") from e

    async def get_lender_metrics(self) -> LenderMetrics:
        logger.info("fetching_lender_metrics")
        try:
            # Submissions by Lender
            submissions_query = select(LenderSubmission.lender_id, func.count(LenderSubmission.id)).group_by(LenderSubmission.lender_id)
            submissions_result = await self.db.execute(submissions_query)
            submissions_by_lender: Dict[str, int] = dict(submissions_result.fetchall())

            # Approval Rates (mock example)
            approval_rate_by_lender: Dict[str, float] = {
                "Bank A": 0.85,
                "Credit Union B": 0.90
            }

            # Avg Rate by Lender (mock example)
            avg_rate_by_lender: Dict[str, Decimal] = {
                "Bank A": Decimal('0.045'),
                "Credit Union B": Decimal('0.042')
            }

            return LenderMetrics(
                submissions_by_lender=submissions_by_lender,
                approval_rate_by_lender=approval_rate_by_lender,
                avg_rate_by_lender=avg_rate_by_lender
            )
        except Exception as e:
            logger.error("lender_metrics_error", exc_info=e)
            raise AppException("Failed to fetch lender metrics") from e

    async def export_applications_csv(self) -> str:
        logger.info("exporting_applications_csv")
        try:
            query = select(Application.id, Application.client_id, Application.property_address, Application.loan_amount, Application.status, Application.created_at)
            result = await self.db.execute(query)
            rows = result.fetchall()

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'Client ID', 'Property Address', 'Loan Amount', 'Status', 'Created At'])
            for row in rows:
                writer.writerow(row)
            return output.getvalue()
        except Exception as e:
            logger.error("csv_export_error", exc_info=e)
            raise AppException("Failed to export applications CSV") from e

    async def get_fintrac_summary(self) -> List[FintracSummaryResponse]:
        logger.info("fetching_fintrac_summary")
        try:
            query = select(FintracReportSummary)
            result = await self.db.execute(query)
            summaries = result.scalars().all()
            return [FintracSummaryResponse.model_validate(summary) for summary in summaries]
        except Exception as e:
            logger.error("fintrac_summary_error", exc_info=e)
            raise AppException("Failed to fetch FINTRAC summary") from e