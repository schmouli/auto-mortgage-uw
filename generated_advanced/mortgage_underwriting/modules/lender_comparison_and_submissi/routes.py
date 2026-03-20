from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.lender.schemas import (
    LenderListResponse,
    LenderProductListResponse,
    LenderMatchRequest,
    LenderMatchResponse,
    LenderSubmissionCreate,
    LenderSubmissionUpdate,
    LenderSubmissionListResponse,
    LenderSubmissionSchema
)
from mortgage_underwriting.modules.lender.services import LenderService, LenderSubmissionService

router = APIRouter(prefix="/api/v1/lenders", tags=["Lender Management"])


@router.get("/", response_model=LenderListResponse)
async def list_lenders(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    type: Optional[str] = Query(None, pattern="^(bank|credit_union|monoline|private|mfc)$"),
    db: AsyncSession = Depends(get_async_session)
) -> LenderListResponse:
    """List all active lenders with optional filtering by type."""
    service = LenderService(db)
    return await service.list_lenders(limit=limit, offset=offset, lender_type=type)


@router.get("/{lender_id}/products", response_model=LenderProductListResponse)
async def get_lender_products(
    lender_id: int,
    mortgage_type: Optional[str] = Query(None, pattern="^(fixed|variable|heloc)$"),
    is_active: bool = Query(True),
    db: AsyncSession = Depends(get_async_session)
) -> LenderProductListResponse:
    """Get all products for a specific lender."""
    service = LenderService(db)
    return await service.get_lender_products(lender_id=lender_id, mortgage_type=mortgage_type, is_active=is_active)


@router.post("/match", response_model=LenderMatchResponse)
async def match_lenders(
    payload: LenderMatchRequest,
    db: AsyncSession = Depends(get_async_session)
) -> LenderMatchResponse:
    """Match lenders to an application based on eligibility criteria."""
    service = LenderService(db)
    return await service.match_lenders(payload)


@router.post("/applications/{application_id}/submissions", response_model=LenderSubmissionSchema, status_code=status.HTTP_201_CREATED)
async def create_submission(
    application_id: int,
    payload: LenderSubmissionCreate,
    db: AsyncSession = Depends(get_async_session)
) -> LenderSubmissionSchema:
    """Create a new lender submission record."""
    # Ensure application_id in path matches payload
    if payload.application_id != application_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Application ID mismatch", "error_code": "SUBMISSION_001"}
        )
    
    service = LenderSubmissionService(db)
    return await service.create_submission(payload)


@router.get("/applications/{application_id}/submissions", response_model=LenderSubmissionListResponse)
async def list_submissions(
    application_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session)
) -> LenderSubmissionListResponse:
    """List all submissions for an application."""
    service = LenderSubmissionService(db)
    return await service.list_submissions(application_id=application_id, limit=limit, offset=offset)


@router.put("/applications/{application_id}/submissions/{submission_id}", response_model=LenderSubmissionSchema)
async def update_submission_status(
    application_id: int,
    submission_id: int,
    payload: LenderSubmissionUpdate,
    db: AsyncSession = Depends(get_async_session)
) -> LenderSubmissionSchema:
    """Update the status and other details of a submission."""
    # FIXED: Add validation to ensure application_id matches submission's application_id
    service = LenderSubmissionService(db)
    submission = await service.update_submission_status(submission_id=submission_id, payload=payload)
    
    # Validate that the submission belongs to the specified application
    if submission.application_id != application_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Submission does not belong to specified application", "error_code": "SUBMISSION_002"}
        )
    
    return submission