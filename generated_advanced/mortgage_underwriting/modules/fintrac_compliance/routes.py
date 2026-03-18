from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.fintrac.schemas import (
    FintracVerificationCreate,
    FintracVerificationResponse,
    FintracReportCreate,
    FintracReportResponse,
    RiskAssessmentResponse
)
from mortgage_underwriting.modules.fintrac.services import FintracService

router = APIRouter(prefix="/api/v1/fintrac", tags=["FINTRAC Compliance"])

# TODO: Add authentication dependency
# auth_dep = Depends(get_current_active_user_with_scope("fintrac:write"))

@router.post("/applications/{application_id}/verify-identity", response_model=FintracVerificationResponse, status_code=status.HTTP_201_CREATED)
async def submit_identity_verification(
    application_id: UUID,
    payload: FintracVerificationCreate,
    # user: User = auth_dep,  # Uncomment when auth implemented
    db: AsyncSession = Depends(get_async_session),
) -> FintracVerificationResponse:
    """Submit identity verification for a mortgage application client."""
    service = FintracService(db)
    # In real implementation, get user ID from auth token
    verified_by_user_id = UUID('00000000-0000-0000-0000-000000000000')  # Placeholder
    return await service.create_verification(application_id, payload, verified_by_user_id)

@router.get("/applications/{application_id}/verification", response_model=FintracVerificationResponse)
async def get_verification_status(
    application_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> FintracVerificationResponse:
    """Get the latest verification status for an application."""
    service = FintracService(db)
    verification = await service.get_verification_status(application_id)
    if not verification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No verification found")
    return verification

@router.post("/applications/{application_id}/report-transaction", response_model=FintracReportResponse, status_code=status.HTTP_201_CREATED)
async def file_transaction_report(
    application_id: UUID,
    payload: FintracReportCreate,
    # user: User = auth_dep,  # Uncomment when auth implemented
    db: AsyncSession = Depends(get_async_session),
) -> FintracReportResponse:
    """File a FINTRAC transaction report for an application."""
    service = FintracService(db)
    # In real implementation, get user ID from auth token
    created_by_user_id = UUID('00000000-0000-0000-0000-000000000000')  # Placeholder
    return await service.create_transaction_report(application_id, payload, created_by_user_id)

@router.get("/applications/{application_id}/reports", response_model=List[FintracReportResponse])
async def list_fintrac_reports(
    application_id: UUID,
    limit: int = Query(100, le=100, ge=1, description="Max results (max 100)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_async_session),
) -> List[FintracReportResponse]:
    """List FINTRAC reports for an application with pagination."""
    service = FintracService(db)
    return await service.list_reports(application_id, limit, offset)

@router.get("/risk-assessment/{client_id}", response_model=RiskAssessmentResponse)
async def get_client_risk_assessment(
    client_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> RiskAssessmentResponse:
    """Get client's current risk assessment based on latest verification."""
    service = FintracService(db)
    return await service.get_risk_assessment(client_id)