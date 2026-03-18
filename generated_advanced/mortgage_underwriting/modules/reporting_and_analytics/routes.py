from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import csv
import io
from fastapi import APIRouter, Depends, Query, Response, status
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.reporting.schemas import (
    PipelineReportResponse, VolumeReportResponse, LenderReportResponse,
    FintracSummaryResponse, PipelineQueryParams, VolumeQueryParams
)
from mortgage_underwriting.modules.reporting.services import ReportingService
from mortgage_underwriting.common.exceptions import AppException
from mortgage_underwriting.modules.mortgage.models import MortgageApplication

router = APIRouter(prefix="/api/v1/reports", tags=["Reporting & Analytics"])


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise AppException(detail="Invalid date format. Expected YYYY-MM-DD.", error_code="REPORTING_004") from e


@router.get("/pipeline", response_model=PipelineReportResponse)
async def get_pipeline_report(
    start_date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$'),
    end_date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$'),
    lender_id: Optional[int] = Query(None, gt=0),
    db: AsyncSession = Depends(get_async_session)
) -> PipelineReportResponse:
    """Get pipeline status summary with filtering options."""
    service = ReportingService(db)
    parsed_start = parse_date(start_date)
    parsed_end = parse_date(end_date)
    
    if parsed_start and parsed_end and parsed_start > parsed_end:
        raise AppException(
            detail="Invalid date range: start_date must be before or equal to end_date",
            error_code="REPORTING_001"
        )
        
    return await service.get_pipeline_report(parsed_start, parsed_end, lender_id)


@router.get("/volume", response_model=VolumeReportResponse)
async def get_volume_report(
    period: str = Query(..., regex='^(monthly|quarterly|ytd)$'),
    property_type: Optional[str] = Query(None, regex='^(single_family|condo|multi_unit|commercial)$'),
    application_type: Optional[str] = Query(None, regex='^(purchase|refinance|renewal|switch)$'),
    db: AsyncSession = Depends(get_async_session)
) -> VolumeReportResponse:
    """Get volume metrics for specified period and filters."""
    service = ReportingService(db)
    return await service.get_volume_report(period, property_type, application_type)


@router.get("/lenders", response_model=LenderReportResponse)
async def get_lender_report(
    db: AsyncSession = Depends(get_async_session)
) -> LenderReportResponse:
    """Get lender performance breakdown."""
    service = ReportingService(db)
    return await service.get_lender_report()


@router.get("/applications/export")
async def export_applications_csv(
    response: Response,
    start_date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$'),
    end_date: Optional[str] = Query(None, regex=r'^\d{4}-\d{2}-\d{2}$'),
    lender_id: Optional[int] = Query(None, gt=0),
    db: AsyncSession = Depends(get_async_session)
) -> Response:
    """Export applications as CSV for given period and filters."""
    # This is a simplified version - in practice would join multiple tables
    parsed_start = parse_date(start_date)
    parsed_end = parse_date(end_date)
    
    stmt = select(MortgageApplication)
    if parsed_start and parsed_end:
        stmt = stmt.where(MortgageApplication.created_at.between(parsed_start, parsed_end))
    if lender_id:
        stmt = stmt.where(MortgageApplication.lender_id == lender_id)
        
    result = await db.execute(stmt)
    apps = result.scalars().all()
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Client ID", "Loan Amount", "Status", "Created At"])
    for app in apps:
        writer.writerow([app.id, app.client_id, app.loan_amount, app.status, app.created_at.isoformat()])
    
    csv_data = output.getvalue()
    output.close()
    
    response.headers["Content-Disposition"] = "attachment; filename=applications_export.csv"
    response.headers["Content-Type"] = "text/csv"
    return Response(content=csv_data)


@router.get("/fintrac/summary", response_model=FintracSummaryResponse)
async def get_fintrac_summary(
    report_month: str = Query(..., regex=r'^\d{4}-\d{2}$'),  # YYYY-MM
    db: AsyncSession = Depends(get_async_session)
) -> FintracSummaryResponse:
    """Get FINTRAC compliance summary for a given month."""
    service = ReportingService(db)
    return await service.get_fintrac_summary(report_month)