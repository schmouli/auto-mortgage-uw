from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.fintrac.services import FintracService
from mortgage_underwriting.modules.fintrac.schemas import (
    IdentityVerificationCreateRequest,
    TransactionReportCreateRequest,
    IdentityVerificationResponse,
    TransactionReportResponse,
    VerificationStatusResponse,
    RiskAssessmentResponse,
    ReportsListResponse
)

router = APIRouter(prefix="/api/v1/fintrac", tags=["FINTRAC Compliance"])

@router.post("/applications/{application_id}/verify-identity", response_model=IdentityVerificationResponse)
async def submit_identity_verification(
    *,
    db: AsyncSession = Depends(get_async_session),
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
            changed_by_user_id=request.verified_by
        )
    except Exception as e:
        raise HTTPException(
            status_code=400, 
            detail={"detail": str(e), "error_code": "VERIFICATION_CREATION_FAILED"}
        )

@router.get("/applications/{application_id}/verification", response_model=VerificationStatusResponse)
async def get_verification_status(
    *,
    db: AsyncSession = Depends(get_async_session),
    application_id: int = Path(..., title="Application ID", ge=1)
) -> VerificationStatusResponse:
    """
    Retrieve the latest identity verification status for an application.
    """
    service = FintracService(db)
    try:
        return await service.get_verification_status(application_id)
    except Exception as e:
        raise HTTPException(
            status_code=404 if "not found" in str(e).lower() else 400,
            detail={"detail": str(e), "error_code": "VERIFICATION_RETRIEVAL_FAILED"}
        )

@router.post("/clients/{client_id}/reports", response_model=TransactionReportResponse)
async def file_transaction_report(
    *,
    db: AsyncSession = Depends(get_async_session),
    client_id: int = Path(..., title="Client ID", ge=1),
    request: TransactionReportCreateRequest
) -> TransactionReportResponse:
    """
    File a FINTRAC transaction report for a client.
    
    Used for reporting large cash transactions (>CAD $10,000) and suspicious activities.
    """
    service = FintracService(db)
    try:
        return await service.file_transaction_report(client_id, request)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"detail": str(e), "error_code": "REPORT_SUBMISSION_FAILED"}
        )

@router.get("/clients/{client_id}/reports", response_model=ReportsListResponse)
async def list_transaction_reports(
    *,
    db: AsyncSession = Depends(get_async_session),
    client_id: int = Path(..., title="Client ID", ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)  # FIXED: Added max limit enforcement
) -> ReportsListResponse:
    """
    List transaction reports for a client with pagination.
    
    Maximum 100 records per page to ensure performance.
    """
    service = FintracService(db)
    try:
        reports, total = await service.list_transaction_reports(client_id, skip, limit)
        return ReportsListResponse(
            reports=reports,
            total=total,
            page=skip // limit + 1 if limit > 0 else 1,
            size=len(reports)
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"detail": str(e), "error_code": "REPORT_LISTING_FAILED"}
        )

@router.get("/clients/{client_id}/risk-assessment", response_model=RiskAssessmentResponse)
async def get_client_risk_assessment(
    *,
    db: AsyncSession = Depends(get_async_session),
    client_id: int = Path(..., title="Client ID", ge=1)
) -> RiskAssessmentResponse:
    """
    Generate a risk assessment for a client based on their verification history.
    """
    service = FintracService(db)
    try:
        return await service.get_client_risk_assessment(client_id)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"detail": str(e), "error_code": "RISK_ASSESSMENT_FAILED"}
        )
```

```