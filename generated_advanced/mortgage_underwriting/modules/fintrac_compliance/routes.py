from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.fintrac.schemas import (
    VerifyIdentityRequest,
    VerifyIdentityResponse,
    ReportTransactionRequest,
    ReportTransactionResponse,
    RiskAssessmentResponse
)
from mortgage_underwriting.modules.fintrac.services import FintracService

router = APIRouter(prefix="/api/v1/fintrac", tags=["FINTRAC Compliance"])

# TODO: Add authentication dependency
# async def get_current_user(...) -> User: ...

@router.post(
    "/applications/{application_id}/verify-identity",
    response_model=VerifyIdentityResponse,
    status_code=status.HTTP_201_CREATED
)
async def verify_identity_endpoint(
    application_id: int = Path(..., gt=0),
    payload: VerifyIdentityRequest = ...,  # In practice would include auth/user context
    db: AsyncSession = Depends(get_async_session)
) -> VerifyIdentityResponse:
    """Submit identity verification for a client on a mortgage application."""
    try:
        service = FintracService(db)
        # In practice, current_user_id would come from auth middleware
        current_user_id = 1  # Placeholder
        return await service.verify_identity(application_id, current_user_id, payload)
    except Exception as e:
        if hasattr(e, 'status_code'):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "FINTRAC_009"}
        )

@router.get(
    "/applications/{application_id}/verification",
    response_model=VerifyIdentityResponse
)
async def get_verification_status_endpoint(
    application_id: int = Path(..., gt=0),
    client_id: int = Query(..., gt=0),  # Query param in practice
    db: AsyncSession = Depends(get_async_session)
) -> VerifyIdentityResponse:
    """Get verification status for a client on an application."""
    try:
        service = FintracService(db)
        result = await service.get_verification_status(application_id, client_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"detail": "Verification not found", "error_code": "FINTRAC_004"}
            )
        return result
    except Exception as e:
        if hasattr(e, 'status_code'):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "FINTRAC_010"}
        )

@router.post(
    "/applications/{application_id}/report-transaction",
    response_model=ReportTransactionResponse,
    status_code=status.HTTP_201_CREATED
)
async def report_transaction_endpoint(
    application_id: int = Path(..., gt=0),
    payload: ReportTransactionRequest = ...,
    db: AsyncSession = Depends(get_async_session)
) -> ReportTransactionResponse:
    """File a FINTRAC transaction report."""
    try:
        service = FintracService(db)
        # In practice, current_user_id would come from auth middleware
        current_user_id = 1  # Placeholder
        return await service.report_transaction(application_id, current_user_id, payload)
    except Exception as e:
        if hasattr(e, 'status_code'):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "FINTRAC_011"}
        )

@router.get(
    "/applications/{application_id}/reports",
    response_model=List[ReportTransactionResponse]
)
async def get_reports_endpoint(
    application_id: int = Path(..., gt=0),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session)
) -> List[ReportTransactionResponse]:
    """List FINTRAC reports for an application."""
    try:
        service = FintracService(db)
        reports = await service.get_reports(application_id)
        return reports[offset:offset+limit]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "FINTRAC_012"}
        )

@router.get(
    "/risk-assessment/{client_id}",
    response_model=RiskAssessmentResponse
)
async def get_risk_assessment_endpoint(
    client_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_async_session)
) -> RiskAssessmentResponse:
    """Get client risk assessment."""
    try:
        service = FintracService(db)
        return await service.get_risk_assessment(client_id)
    except Exception as e:
        if hasattr(e, 'status_code'):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "FINTRAC_013"}
        )