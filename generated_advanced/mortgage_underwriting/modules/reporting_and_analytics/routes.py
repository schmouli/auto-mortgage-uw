from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
import structlog

from mortgage_underwriting.common.database import get_async_session
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
from mortgage_underwriting.modules.reporting.services import ReportingService

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/reports", tags=["Reporting & Analytics"])


@router.get("/pipeline", response_model=PipelineSummaryResponse)
async def get_pipeline_report(
    filters: PipelineReportQuery = Depends(),
    db: AsyncSession = Depends(get_async_session)
) -> PipelineSummaryResponse:
    """Retrieve pipeline status summary with stage duration and approval metrics."""
    try:
        service = ReportingService(db)
        return await service.get_pipeline_summary(filters)
    except Exception as e:
        logger.error("pipeline_report_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to generate pipeline report", "error_code": "REPORTING_005"}
        )


@router.get("/volume", response_model=VolumeMetricsResponse)
async def get_volume_report(
    filters: VolumeReportQuery = Depends(),
    db: AsyncSession = Depends(get_async_session)
) -> VolumeMetricsResponse:
    """Get volume metrics including trends and averages."""
    try:
        service = ReportingService(db)
        return await service.get_volume_metrics(filters)
    except Exception as e:
        logger.error("volume_report_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to calculate volume metrics", "error_code": "REPORTING_006"}
        )


@router.get("/lenders", response_model=LenderPerformanceResponse)
async def get_lender_report(
    filters: LenderReportQuery = Depends(),
    db: AsyncSession = Depends(get_async_session)
) -> LenderPerformanceResponse:
    """Get lender performance breakdown."""
    try:
        service = ReportingService(db)
        return await service.get_lender_performance(filters)
    except Exception as e:
        logger.error("lender_report_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to analyze lender performance", "error_code": "REPORTING_007"}
        )


@router.get("/fintrac/summary", response_model=FintracComplianceSummary)
async def get_fintrac_compliance_summary(
    report_date: str,
    db: AsyncSession = Depends(get_async_session)
) -> FintracComplianceSummary:
    """Get FINTRAC compliance summary for regulatory reporting."""
    try:
        parsed_date = datetime.fromisoformat(report_date)
        service = ReportingService(db)
        return await service.get_fintrac_summary(parsed_date)
    except Exception as e:
        logger.error("fintrac_summary_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to retrieve FINTRAC summary", "error_code": "REPORTING_008"}
        )


@router.post("/applications/export")
async def export_applications_report(
    request: ReportExportRequest,
    response: Response,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_async_session)
) -> Response:
    """Export report data in specified format."""
    try:
        service = ReportingService(db)
        result = await service.export_report_data(request, user_id)
        
        # Return CSV content directly
        response.headers["Content-Disposition"] = f"attachment; filename={result['filename']}"
        response.headers["Content-Type"] = "text/csv"
        return Response(content=result["content"])
        
    except Exception as e:
        logger.error("export_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Failed to export report data", "error_code": "REPORTING_009"}
        )