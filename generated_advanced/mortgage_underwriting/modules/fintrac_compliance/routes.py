from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.fintrac.schemas import (
    FintracVerificationRequest,
    FintracTransactionReportRequest,
    FintracVerificationResponse,
    FintracVerificationStatusResponse,
    FintracReportListResponse,
    FintracRiskAssessmentResponse
)
from mortgage_underwriting.modules.fintrac.services import FintracComplianceService

router = APIRouter(prefix="/api/v1/fintrac", tags=["FINTRAC Compliance"])

@router.post(
    "/applications/{application_id}/verify-identity",
    response_model=FintracVerificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Identity Verification"
)
async def verify_identity(
    application_id: int,
    payload: FintracVerificationRequest,
    created_by: int = Query(..., description="User ID creating the record"),
    db: AsyncSession = Depends(get_async_session),
) -> FintracVerificationResponse:
    """Submit identity verification for a client associated with a mortgage application."""
    try:
        service = FintracComplianceService(db)
        return await service.verify_identity(application_id, payload, created_by)
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                "detail": str(e),
                "error_code": e.error_code
            })
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
            "detail": "An unexpected error occurred",
            "error_code": "INTERNAL_ERROR"
        })

@router.get(
    "/applications/{application_id}/verification",
    response_model=List[FintracVerificationStatusResponse],
    summary="Get Verification Status"
)
async def get_verification_status(
    application_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> List[FintracVerificationStatusResponse]:
    """Get verification status for a mortgage application."""
    try:
        service = FintracComplianceService(db)
        return await service.get_verification_status(application_id)
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                "detail": str(e),
                "error_code": e.error_code
            })
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
            "detail": "An unexpected error occurred",
            "error_code": "INTERNAL_ERROR"
        })

@router.post(
    "/applications/{application_id}/report-transaction",
    response_model=FintracReportListResponse,
    status_code=status.HTTP_201_CREATED,
    summary="File Transaction Report"
)
async def report_transaction(
    application_id: int,
    payload: FintracTransactionReportRequest,
    created_by: int = Query(..., description="User ID creating the record"),
    db: AsyncSession = Depends(get_async_session),
) -> FintracReportListResponse:
    """File a FINTRAC transaction report for an application."""
    try:
        service = FintracComplianceService(db)
        return await service.report_transaction(application_id, payload, created_by)
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                "detail": str(e),
                "error_code": e.error_code
            })
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
            "detail": "An unexpected error occurred",
            "error_code": "INTERNAL_ERROR"
        })

@router.get(
    "/applications/{application_id}/reports",
    response_model=List[FintracReportListResponse],
    summary="List FINTRAC Reports"
)
async def list_reports(
    application_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> List[FintracReportListResponse]:
    """List all FINTRAC reports for an application."""
    try:
        service = FintracComplianceService(db)
        return await service.list_reports(application_id)
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                "detail": str(e),
                "error_code": e.error_code
            })
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
            "detail": "An unexpected error occurred",
            "error_code": "INTERNAL_ERROR"
        })

@router.get(
    "/risk-assessment/{client_id}",
    response_model=FintracRiskAssessmentResponse,
    summary="Get Client Risk Assessment"
)
async def get_risk_assessment(
    client_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> FintracRiskAssessmentResponse:
    """Get risk assessment for a client."""
    try:
        service = FintracComplianceService(db)
        return await service.get_risk_assessment(client_id)
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                "detail": str(e),
                "error_code": e.error_code
            })
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
            "detail": "An unexpected error occurred",
            "error_code": "INTERNAL_ERROR"
        })