from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from mortgage_underwriter.modules.orchestrator.schemas import (

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.orchestrator.services import OrchestratorService

    ApplicationSubmitRequest,
    ApplicationSubmitResponse,
    ApplicationResponse,
    DocumentResponse,
    FintracVerificationRequest,
    FintracVerificationResponse,
    FintracTransactionReportRequest,
    RiskAssessmentResponse,
    PaginatedApplicationResponse
)

router = APIRouter(prefix="/api/v1/applications", tags=["Orchestrator"])


def get_orchestrator_service(db: AsyncSession = Depends(get_async_session)) -> OrchestratorService:
    return OrchestratorService(db)


@router.post("/", response_model=ApplicationSubmitResponse, status_code=status.HTTP_201_CREATED)


async def submit_application(
    payload: ApplicationSubmitRequest,
    service: OrchestratorService = Depends(get_orchestrator_service)
):
    """Submit a new mortgage application."""
    try:
        return await service.submit_application(payload)
    except Exception as e:
        if hasattr(e, 'detail') and hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                "detail": e.detail,
                "error_code": e.error_code
            })
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
            "detail": "Internal server error",
            "error_code": "ORCHESTRATOR_001"
        })


@router.get("/{application_id}", response_model=ApplicationResponse)


async def get_application(
    application_id: str,
    service: OrchestratorService = Depends(get_orchestrator_service)
):
    """Get application by ID."""
    try:
        return await service.get_application(application_id)
    except Exception as e:
        if hasattr(e, 'detail') and hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                "detail": e.detail,
                "error_code": e.error_code
            })
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
            "detail": "Internal server error",
            "error_code": "ORCHESTRATOR_001"
        })


@router.get("/", response_model=PaginatedApplicationResponse)


async def list_applications(
    page: int = 1,
    size: int = 50,
    service: OrchestratorService = Depends(get_orchestrator_service)
):
    """List all applications with pagination."""
    try:
        return await service.list_applications(page, size)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
            "detail": "Internal server error",
            "error_code": "ORCHESTRATOR_001"
        })


@router.get("/{application_id}/documents", response_model=List[DocumentResponse])


async def list_application_documents(
    application_id: str,
    service: OrchestratorService = Depends(get_orchestrator_service)
):
    """List uploaded documents for an application."""
    try:
        return await service.get_application_documents(application_id)
    except Exception as e:
        if hasattr(e, 'detail') and hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                "detail": e.detail,
                "error_code": e.error_code
            })
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
            "detail": "Internal server error",
            "error_code": "ORCHESTRATOR_001"
        })


@router.post("/{application_id}/reprocess")


async def reprocess_application(
    application_id: str,
    service: OrchestratorService = Depends(get_orchestrator_service)
):
    """Trigger reprocessing of an application."""
    # This would trigger async tasks in a real implementation
    return {"message": f"Reprocessing initiated for application {application_id}"}


# FINTRAC Routes
@router.post("/fintrac/applications/{application_id}/verify-identity", response_model=FintracVerificationResponse)


async def verify_identity(
    application_id: str,
    payload: FintracVerificationRequest,
    service: OrchestratorService = Depends(get_orchestrator_service)
):
    """Submit identity verification for FINTRAC compliance."""
    try:
        return await service.verify_identity(application_id, payload)
    except Exception as e:
        if hasattr(e, 'detail') and hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                "detail": e.detail,
                "error_code": e.error_code
            })
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
            "detail": "Internal server error",
            "error_code": "ORCHESTRATOR_001"
        })


@router.get("/fintrac/applications/{application_id}/verification", response_model=FintracVerificationResponse)


async def get_fintrac_verification_status(
    application_id: str,
    service: OrchestratorService = Depends(get_orchestrator_service)
):
    """Get FINTRAC verification status."""
    try:
        return await service.get_fintrac_verification_status(application_id)
    except Exception as e:
        if hasattr(e, 'detail') and hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={
                "detail": e.detail,
                "error_code": e.error_code
            })
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
            "detail": "Internal server error",
            "error_code": "ORCHESTRATOR_001"
        })


@router.post("/fintrac/applications/{application_id}/report-transaction", response_model=FintracVerificationResponse)


async def report_transaction(
    application_id: str,
    payload: FintracTransactionReportRequest,
    service: OrchestratorService = Depends(get_orchestrator_service)
):
    """File FINTRAC transaction report."""
    try:
        return await service.report_transaction(application_id, payload)
    except Exception as e:
        if hasattr(e, 'detail') and hasattr(e, 'error_code'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
                "detail": e.detail,
                "error_code": e.error_code
            })
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
            "detail": "Internal server error",
            "error_code": "ORCHESTRATOR_001"
        })


@router.get("/fintrac/risk-assessment/{client_id}", response_model=RiskAssessmentResponse)


async def get_client_risk_assessment(
    client_id: int,
    service: OrchestratorService = Depends(get_orchestrator_service)
):
    """Get client risk assessment."""
    try:
        return await service.get_risk_assessment(client_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={
            "detail": "Internal server error",
            "error_code": "ORCHESTRATOR_001"
        })