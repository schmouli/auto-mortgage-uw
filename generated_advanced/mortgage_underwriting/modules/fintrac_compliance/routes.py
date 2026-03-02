```python
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api.deps import get_db, get_current_active_user
from app.models.user import User
from app.services.fintrac_service import FintracService
from app.schemas.fintrac_compliance import (
    IdentityVerificationCreateRequest,
    TransactionReportCreateRequest,
    IdentityVerificationResponse,
    TransactionReportResponse,
    VerificationStatusResponse,
    RiskAssessmentResponse,
    ReportsListResponse
)

router = APIRouter(prefix="/fintrac", tags=["FINTRAC Compliance"])

@router.post("/applications/{application_id}/verify-identity", response_model=IdentityVerificationResponse)
async def submit_identity_verification(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    application_id: int = Path(..., title="Application ID", ge=1),
    request: IdentityVerificationCreateRequest
) -> IdentityVerificationResponse:
    """
    Submit identity verification for a mortgage application.
    
    This endpoint creates a new identity verification record which includes:
    - Verification method details
    - Encrypted identification information
    - Risk assessment flags (PEP/HIO status)
    - Automatic risk level determination
    
    All personally identifiable information is encrypted at rest.
    """
    service = FintracService(db)
    try:
        return await service.create_identity_verification(
            application_id=application_id,
            client_id=request.verified_by,  # In real implementation, this should come from application
            request=request,
            changed_by_user_id=current_user.id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/applications/{application_id}/verification", response_model=VerificationStatusResponse)
async def get_verification_status(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    application_id: int = Path(..., title="Application ID", ge=1)
) -> VerificationStatusResponse:
    """
    Get the current verification status for an application.
    
    Returns whether the application has been verified and if enhanced due diligence is required.
    """
    service = FintracService(db)
    try:
        return await service.get_verification_status(application_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/applications/{application_id}/report-transaction", response_model=TransactionReportResponse)
async def file_transaction_report(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    application_id: int = Path(..., title="Application ID", ge=1),
    request: TransactionReportCreateRequest
) -> TransactionReportResponse:
    """
    File a transaction report to FINTRAC.
    
    Automatically detects potential structuring attempts when multiple cash transactions
    under $10,000 occur within 24 hours and converts them to suspicious transaction reports.
    
    Only Canadian dollar transactions are checked for structuring.
    """
    service = FintracService(db)
    try:
        return await service.file_transaction_report(
            application_id=application_id,
            request=request,
            changed_by_user_id=current_user.id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/applications/{application_id}/reports", response_model=ReportsListResponse)
async def list_transaction_reports(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    application_id: int = Path(..., title="Application ID", ge=1)
) -> ReportsListResponse:
    """
    List all FINTRAC reports filed for an application.
    
    Returns reports sorted by date, newest first. Deleted reports are excluded.
    """
    service = FintracService(db)
    try:
        reports = await service.list_transaction_reports(application_id)
        return ReportsListResponse(reports=reports, total_count=len(reports))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/risk-assessment/{client_id}", response_model=RiskAssessmentResponse)
async def get_client_risk_assessment(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    client_id: int = Path(..., title="Client ID", ge=1)
) -> RiskAssessmentResponse:
    """
    Get the current risk assessment for a client.
    
    Includes information about whether enhanced due diligence is required based on:
    - Current risk level
    - Politically exposed person status
    - High impact organization status
    """
    service = FintracService(db)
    try:
        return await service.get_client_risk_assessment(client_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
```