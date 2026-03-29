from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.lender.schemas import (
    LenderResponse,
    LenderProductResponse,
    LenderSubmissionCreate,
    LenderSubmissionUpdate,
    LenderSubmissionResponse,
    LenderMatchRequest,
    LenderMatchResult,
    SubmissionPackageRequest
)
from mortgage_underwriting.modules.lender.services import LenderService

router = APIRouter(prefix="/api/v1/lenders", tags=["Lender Management"])


def get_lender_service(db: AsyncSession = Depends(get_async_session)) -> LenderService:
    return LenderService(db)


@router.get("/", response_model=List[LenderResponse])
async def list_lenders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: LenderService = Depends(get_lender_service)
) -> List[LenderResponse]:
    """List all active lenders with pagination."""
    try:
        return await service.get_lenders(skip=skip, limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "LENDER_FETCH_ERROR", "detail": str(e)}
        )


@router.get("/{lender_id}/products", response_model=List[LenderProductResponse])
async def list_lender_products(
    lender_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: LenderService = Depends(get_lender_service)
) -> List[LenderProductResponse]:
    """Get products for a specific lender."""
    try:
        return await service.get_lender_products(lender_id=lender_id, skip=skip, limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "PRODUCT_FETCH_ERROR", "detail": str(e)}
        )


@router.post("/match", response_model=List[LenderMatchResult])
async def match_lenders(
    payload: LenderMatchRequest,
    service: LenderService = Depends(get_lender_service)
) -> List[LenderMatchResult]:
    """Match lenders to an application based on qualification criteria."""
    try:
        return await service.match_lenders(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "MATCHING_ERROR", "detail": str(e)}
        )


@router.post("/submissions", response_model=LenderSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    payload: LenderSubmissionCreate,
    service: LenderService = Depends(get_lender_service)
) -> LenderSubmissionResponse:
    """Create a new lender submission record."""
    try:
        return await service.create_submission(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "SUBMISSION_CREATE_ERROR", "detail": str(e)}
        )


@router.get("/applications/{application_id}/submissions", response_model=List[LenderSubmissionResponse])
async def list_submissions(
    application_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: LenderService = Depends(get_lender_service)
) -> List[LenderSubmissionResponse]:
    """List submissions for an application."""
    try:
        return await service.get_submissions(application_id=application_id, skip=skip, limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "SUBMISSIONS_FETCH_ERROR", "detail": str(e)}
        )


@router.put("/applications/{application_id}/submissions/{submission_id}", response_model=LenderSubmissionResponse)
async def update_submission(
    application_id: int,
    submission_id: int,
    payload: LenderSubmissionUpdate,
    service: LenderService = Depends(get_lender_service)
) -> LenderSubmissionResponse:
    """Update a submission status or details."""
    try:
        return await service.update_submission(submission_id=submission_id, payload=payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "SUBMISSION_UPDATE_ERROR", "detail": str(e)}
        )


@router.post("/packages/generate")
async def generate_submission_package(
    payload: SubmissionPackageRequest,
    service: LenderService = Depends(get_lender_service)
) -> dict:
    """Generate a complete submission package including UW results and matched products."""
    try:
        return await service.generate_submission_package(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "PACKAGE_GENERATION_ERROR", "detail": str(e)}
        )