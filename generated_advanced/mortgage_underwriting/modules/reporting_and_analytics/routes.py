from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.auth.dependencies import get_current_user
from mortgage_underwriting.modules.user.models import User

from .schemas import (
    PipelineReportRequest,
    VolumeReportRequest,
    LenderReportRequest,
    ReportExportRequest,
    PipelineSummaryResponse,
    VolumeMetricsResponse,
    LenderPerformanceResponse,
    FintracSummaryResponse
)
from .services import ReportingService

router = APIRouter(prefix="/api/v1/reports", tags=["Reporting & Analytics"])


def require_reporting_access(user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure user has reporting access."""
    allowed_roles = {'underwriter', 'manager', 'admin'}
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Insufficient permissions for reporting", "error_code": "REPORTING_002"}
        )
    return user


@router.get("/pipeline", response_model=PipelineSummaryResponse)
async def get_pipeline_report(
    request: Annotated[PipelineReportRequest, Depends()],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    _: Annotated[User, Depends(require_reporting_access)]
) -> PipelineSummaryResponse:
    """Retrieve pipeline status summary with stage durations and approval metrics."""
    if request.start_date and request.end_date and request.start_date > request.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid date range: start_date cannot be after end_date", "error_code": "REPORTING_001"}
        )
        
    service = ReportingService(db)
    return await service.get_pipeline_summary(request)


@router.get("/volume", response_model=VolumeMetricsResponse)
async def get_volume_report(
    request: Annotated[VolumeReportRequest, Depends()],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    _: Annotated[User, Depends(require_reporting_access)]
) -> VolumeMetricsResponse:
    """Retrieve mortgage volume metrics by period with deal size analytics."""
    if request.start_date and request.end_date and request.start_date > request.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid date range: start_date cannot be after end_date", "error_code": "REPORTING_001"}
        )
        
    service = ReportingService(db)
    return await service.get_volume_metrics(request)


@router.get("/lenders", response_model=LenderPerformanceResponse)
async def get_lender_report(
    request: Annotated[LenderReportRequest, Depends()],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    _: Annotated[User, Depends(require_reporting_access)]
) -> LenderPerformanceResponse:
    """Retrieve lender performance breakdown with submission rates and average rates."""
    if request.start_date and request.end_date and request.start_date > request.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid date range: start_date cannot be after end_date", "error_code": "REPORTING_001"}
        )
        
    service = ReportingService(db)
    return await service.get_lender_performance(request)


@router.get("/applications/export")
async def export_applications_report(
    request: Annotated[ReportExportRequest, Depends()],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    _: Annotated[User, Depends(require_reporting_access)]
) -> Response:
    """Export applications data as downloadable CSV file."""
    if request.start_date and request.end_date and request.start_date > request.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid date range: start_date cannot be after end_date", "error_code": "REPORTING_001"}
        )
        
    service = ReportingService(db)
    csv_data = await service.export_applications(request)
    
    headers = {
        'Content-Disposition': 'attachment; filename="applications_export.csv"',
        'Content-Type': 'text/csv'
    }
    return Response(content=csv_data, headers=headers)


@router.get("/fintrac/summary", response_model=FintracSummaryResponse)
async def get_fintrac_summary_report(
    request: Annotated[LenderReportRequest, Depends()],
    db: Annotated[AsyncSession, Depends(get_async_session)],
    _: Annotated[User, Depends(require_reporting_access)]
) -> FintracSummaryResponse:
    """Retrieve FINTRAC compliance summary for high-value transactions."""
    if request.start_date and request.end_date and request.start_date > request.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid date range: start_date cannot be after end_date", "error_code": "REPORTING_001"}
        )
        
    service = ReportingService(db)
    return await service.get_fintrac_summary(request)