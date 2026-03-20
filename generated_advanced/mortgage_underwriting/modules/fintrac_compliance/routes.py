from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.fintrac.schemas import (
    IdentityVerificationCreate,
    IdentityVerificationResponse,
    TransactionReportCreate,
    TransactionReportResponse,
    RiskAssessmentResponse
)
from mortgage_underwriting.modules.fintrac.services import FintracComplianceService

router = APIRouter(prefix="/api/v1/fintrac", tags=["FINTRAC Compliance"])

# In a real implementation, you would have proper authentication dependency here
# For example: current_user = Depends(get_current_active_user)

@router.post(
    "/applications/{application_id}/verify-identity",
    response_model=IdentityVerificationResponse,
    status_code=status.HTTP_201_CREATED
)
async def verify_client_identity(
    application_id: int,
    payload: IdentityVerificationCreate,
    db: AsyncSession = Depends(get_async_session),
    # current_user = Depends(get_current_active_user)  # Add proper auth
) -> IdentityVerificationResponse:
    """Submit identity verification for a client in an application."""
    service = FintracComplianceService(db)
    try:
        # In a real implementation, you would pass current_user.id
        verification = await service.verify_identity(application_id, payload, verified_by_user_id=1)
        return verification
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/applications/{application_id}/verification",
    response_model=IdentityVerificationResponse
)
async def get_verification_status(
    application_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> IdentityVerificationResponse:
    """Get verification status for an application."""
    service = FintracComplianceService(db)
    verification = await service.get_verification_status(application_id)
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Verification not found", "error_code": "FINTRAC_007"}
        )
    return verification

@router.post(
    "/applications/{application_id}/report-transaction",
    response_model=TransactionReportResponse,
    status_code=status.HTTP_201_CREATED
)
async def file_transaction_report(
    application_id: int,
    payload: TransactionReportCreate,
    db: AsyncSession = Depends(get_async_session),
    # current_user = Depends(get_current_active_user)  # Add proper auth
) -> TransactionReportResponse:
    """File a FINTRAC transaction report."""
    service = FintracComplianceService(db)
    try:
        # In a real implementation, you would pass current_user.id
        report = await service.file_transaction_report(application_id, payload, created_by_user_id=1)
        return report
    except Exception as e:
        if hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": str(e), "error_code": e.error_code})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/applications/{application_id}/reports",
    response_model=List[TransactionReportResponse]
)
async def list_transaction_reports(
    application_id: int,
    skip: int = 0,
    limit: int = Query(100, le=100),  # Max 100 per page
    db: AsyncSession = Depends(get_async_session)
) -> List[TransactionReportResponse]:
    """List FINTRAC reports for an application with pagination."""
    service = FintracComplianceService(db)
    reports = await service.list_transaction_reports(application_id)
    return reports[skip : skip + limit]

@router.get(
    "/risk-assessment/{client_id}",
    response_model=RiskAssessmentResponse
)
async def get_client_risk_assessment(
    client_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> RiskAssessmentResponse:
    """Get client risk assessment."""
    service = FintracComplianceService(db)
    assessment = await service.get_risk_assessment(client_id)
    return assessment