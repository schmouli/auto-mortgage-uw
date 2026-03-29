from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.orchestrator.schemas import (
    ApplicationCreateSchema,
    ApplicationSchema,
    ApplicationListSchema,
    IdentityVerificationRequest,
    IdentityVerificationResponse,
    TransactionReportRequest,
    RiskAssessmentResponse,
)
from mortgage_underwriting.modules.orchestrator.services import OrchestratorService

router = APIRouter(prefix="/api/v1/applications", tags=["Orchestrator Service"])


def get_current_user():
    # Stub for authentication
    return "test@example.com"


@router.post("/", response_model=ApplicationSchema, status_code=status.HTTP_201_CREATED)
async def submit_application(
    payload: ApplicationCreateSchema,
    db: AsyncSession = Depends(get_async_session),
    user_email: str = Depends(get_current_user),
):
    """Submit a new mortgage application and trigger the processing pipeline."""
    try:
        service = OrchestratorService(db)
        return await service.submit_application(payload, user_email)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "SUBMISSION_FAILED"}
        )


@router.get("/{application_id}", response_model=ApplicationSchema)
async def get_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Get application status and decision."""
    try:
        service = OrchestratorService(db)
        return await service.get_application(application_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "APPLICATION_NOT_FOUND"}
        )


@router.get("/", response_model=ApplicationListSchema)
async def list_applications(
    page: int = Query(1, ge=1, le=1000),
    size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
):
    """List all applications with pagination."""
    service = OrchestratorService(db)
    return await service.list_applications(page, size)


@router.post("/{application_id}/reprocess", response_model=dict)
async def reprocess_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Trigger reprocessing of an application."""
    # Implementation would dispatch tasks again
    return {"message": "Reprocessing started", "application_id": application_id}


# FINTRAC Endpoints
fintrac_router = APIRouter(prefix="/api/v1/fintrac", tags=["FINTRAC Compliance"])


@fintrac_router.post("/applications/{application_id}/verify-identity", response_model=IdentityVerificationResponse)
async def verify_identity(
    application_id: UUID,
    payload: IdentityVerificationRequest,
    db: AsyncSession = Depends(get_async_session),
    verified_by: str = Depends(get_current_user),
):
    """Submit identity verification for FINTRAC compliance."""
    service = OrchestratorService(db)
    return await service.verify_identity(application_id, payload, verified_by)


@fintrac_router.get("/applications/{application_id}/verification", response_model=IdentityVerificationResponse)
async def get_verification_status(
    application_id: UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Get FINTRAC verification status."""
    # Stub implementation
    return IdentityVerificationResponse(
        application_id=application_id,
        verified=True,
        verified_at="2023-01-01T00:00:00Z",
        verified_by="compliance_officer@example.com",
    )


@fintrac_router.post("/applications/{application_id}/report-transaction")
async def report_transaction(
    application_id: UUID,
    payload: TransactionReportRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """File FINTRAC transaction report for large transactions."""
    service = OrchestratorService(db)
    return await service.report_transaction(application_id, payload)


@fintrac_router.get("/risk-assessment/{client_id}", response_model=RiskAssessmentResponse)
async def get_client_risk_assessment(
    client_id: UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Get client risk assessment for FINTRAC monitoring."""
    service = OrchestratorService(db)
    return await service.get_risk_assessment(client_id)


# Include nested router
router.include_router(fintrac_router)