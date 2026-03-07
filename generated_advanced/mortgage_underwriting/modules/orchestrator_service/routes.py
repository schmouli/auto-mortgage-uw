from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
import json

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.orchestrator.schemas import (
    ApplicationCreateRequest, ApplicationSubmitResponse, ApplicationStatusResponse,
    DocumentListResponse, FINTRACIdentityVerifyRequest, FINTRACReportTransactionRequest,
    FINTRACVerificationStatusResponse, RiskAssessmentResponse, ApplicationListResponse,
    ReprocessRequest
)
from mortgage_underwriting.modules.orchestrator.services import OrchestratorService
from mortgage_underwriting.modules.orchestrator.models import Application

router = APIRouter(prefix="/api/v1/applications", tags=["Orchestrator Service"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_FILES = 10
ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}


def validate_files(files: List[UploadFile]) -> List[dict]:
    """Validate uploaded files and return metadata."""
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Too many files. Maximum {MAX_FILES} allowed."
        )
    
    validated_docs = []
    for file in files:
        if file.size and file.size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File {file.filename} too large. Max {MAX_FILE_SIZE} bytes."
            )
        
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type for {file.filename}. Allowed: {ALLOWED_MIME_TYPES}"
            )
        
        validated_docs.append({
            "filename": file.filename,
            "size": file.size,
            "content_type": file.content_type
        })
    
    return validated_docs


def simulate_s3_upload(files: List[UploadFile]) -> List[dict]:
    """Simulate uploading files to S3 and return S3 keys and metadata."""
    # In a real implementation, this would actually upload to S3/MinIO
    # and return the S3 keys
    s3_objects = []
    for i, file in enumerate(files):
        s3_objects.append({
            "type": file.filename.split('.')[-1].lower() if '.' in file.filename else "unknown",
            "s3_key": f"uploads/applications/{UUID(int=i)}/{file.filename}",
            "size": file.size or 0,
            "mime_type": file.content_type
        })
    return s3_objects


@router.post("/", response_model=ApplicationSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_application(
    borrower_json: str = Form(...),
    property_value: str = Form(...),  # Will be converted to Decimal
    purchase_price: str = Form(...),
    mortgage_amount: str = Form(...),
    contract_interest_rate: str = Form(...),
    lender_id: str = Form(...),
    documents: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_async_session),
) -> ApplicationSubmitResponse:
    """Submit a new mortgage application with borrower details and documents."""
    try:
        # Convert string forms to proper types
        payload = ApplicationCreateRequest(
            borrower_json=borrower_json,
            property_value=json.loads(property_value),
            purchase_price=json.loads(purchase_price),
            mortgage_amount=json.loads(mortgage_amount),
            contract_interest_rate=json.loads(contract_interest_rate),
            lender_id=lender_id
        )
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Invalid numeric value: {str(e)}", "error_code": "ORCHESTRATOR_001"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Invalid request data: {str(e)}", "error_code": "ORCHESTRATOR_002"}
        )

    # Validate files
    try:
        validate_files(documents)
    except HTTPException:
        raise  # Re-raise file validation errors
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"File validation failed: {str(e)}", "error_code": "ORCHESTRATOR_004"}
        )

    # Simulate S3 upload
    try:
        s3_objects = simulate_s3_upload(documents)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": f"Document upload failed: {str(e)}", "error_code": "ORCHESTRATOR_005"}
        )

    # Process application
    service = OrchestratorService(db)
    try:
        application, celery_task_id = await service.submit_application(payload, s3_objects)
        return ApplicationSubmitResponse(
            application_id=application.id,
            borrower_id=application.borrower_id,
            status=application.status,
            created_at=application.created_at,
            pipeline_task_id=celery_task_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "ORCHESTRATOR_006"}
        )


@router.get("/{application_id}", response_model=ApplicationStatusResponse)
async def get_application_status(
    application_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> ApplicationStatusResponse:
    """Get the status of a specific application."""
    service = OrchestratorService(db)
    try:
        application = await service.get_application_status(application_id)
        return ApplicationStatusResponse.model_validate(application)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "ORCHESTRATOR_007"}
        )


@router.get("/", response_model=ApplicationListResponse)
async def list_applications(
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_async_session),
) -> ApplicationListResponse:
    """List all applications with pagination."""
    service = OrchestratorService(db)
    try:
        apps, total, page_num, page_size = await service.list_applications(page, size)
        return ApplicationListResponse(
            items=[ApplicationStatusResponse.model_validate(app) for app in apps],
            total=total,
            page=page_num,
            size=page_size
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "ORCHESTRATOR_008"}
        )


@router.get("/{application_id}/documents", response_model=List[DocumentListResponse])
async def list_documents(
    application_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> List[DocumentListResponse]:
    """List all documents associated with an application."""
    service = OrchestratorService(db)
    try:
        docs = await service.get_documents(application_id)
        return [DocumentListResponse.model_validate(doc) for doc in docs]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "ORCHESTRATOR_011"}
        )


@router.post("/{application_id}/reprocess", response_model=dict)
async def reprocess_application(
    application_id: UUID,
    payload: ReprocessRequest,
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    """Trigger reprocessing of an application."""
    service = OrchestratorService(db)
    try:
        celery_task_id = await service.reprocess_application(application_id, payload.force)
        return {"message": "Reprocessing initiated", "task_id": celery_task_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "ORCHESTRATOR_012"}
        )


@router.post("/{application_id}/verify-identity", response_model=FINTRACVerificationStatusResponse)
async def verify_identity(
    application_id: UUID,
    payload: FINTRACIdentityVerifyRequest,
    db: AsyncSession = Depends(get_async_session),
) -> FINTRACVerificationStatusResponse:
    """Record identity verification for FINTRAC compliance."""
    service = OrchestratorService(db)
    try:
        report = await service.verify_identity(application_id, payload)
        return FINTRACVerificationStatusResponse.model_validate(report)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "ORCHESTRATOR_013"}
        )


@router.post("/{application_id}/report-transaction", response_model=FINTRACVerificationStatusResponse)
async def report_fintrac_transaction(
    application_id: UUID,
    payload: FINTRACReportTransactionRequest,
    db: AsyncSession = Depends(get_async_session),
) -> FINTRACVerificationStatusResponse:
    """Report a financial transaction for FINTRAC compliance."""
    service = OrchestratorService(db)
    try:
        report = await service.report_fintrac_transaction(application_id, payload)
        return FINTRACVerificationStatusResponse.model_validate(report)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": str(e), "error_code": "ORCHESTRATOR_014"}
        )