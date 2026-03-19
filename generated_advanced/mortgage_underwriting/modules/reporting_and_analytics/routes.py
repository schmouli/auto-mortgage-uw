from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from fastapi import APIRouter, Depends, Query, Response

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.reporting.schemas import PipelineMetrics, VolumeMetrics, LenderMetrics, FintracSummaryResponse, PeriodEnum
from mortgage_underwriting.modules.reporting.services import ReportingService

router = APIRouter(prefix="/api/v1/reports", tags=["Reporting & Analytics"])


@router.get("/pipeline", response_model=PipelineMetrics)
async def get_pipeline_report(
    db: AsyncSession = Depends(get_async_session),
) -> PipelineMetrics:
    """Get pipeline status summary."""
    service = ReportingService(db)
    return await service.get_pipeline_metrics()


@router.get("/volume", response_model=VolumeMetrics)
async def get_volume_report(
    period: PeriodEnum = Query(...),
    db: AsyncSession = Depends(get_async_session),
) -> VolumeMetrics:
    """Get volume metrics for specified period."""
    service = ReportingService(db)
    return await service.get_volume_metrics(period)


@router.get("/lenders", response_model=LenderMetrics)
async def get_lender_report(
    db: AsyncSession = Depends(get_async_session),
) -> LenderMetrics:
    """Get lender performance breakdown."""
    service = ReportingService(db)
    return await service.get_lender_metrics()


@router.get("/applications/export", response_class=Response)
async def export_applications(
    db: AsyncSession = Depends(get_async_session),
) -> Response:
    """Export all applications as CSV."""
    service = ReportingService(db)
    csv_data = await service.export_applications_csv()
    headers = {
        'Content-Disposition': 'attachment; filename="applications.csv"',
        'Content-Type': 'text/csv'
    }
    return Response(content=csv_data, headers=headers)


@router.get("/fintrac/summary", response_model=List[FintracSummaryResponse])
async def get_fintrac_summary(
    db: AsyncSession = Depends(get_async_session),
) -> List[FintracSummaryResponse]:
    """Get FINTRAC compliance summary."""
    service = ReportingService(db)
    return await service.get_fintrac_summary()