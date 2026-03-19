from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.lender_comparison_submission.schemas import (

    LenderResponse,
    LenderProductResponse,
    LenderSubmissionCreate,
    LenderSubmissionUpdate,
    LenderSubmissionResponse,
    LenderMatchRequest,
    LenderMatchResponse
)
from mortgage_underwriting.modules.lender_comparison_submission.services import (
    LenderComparisonService,
    LenderSubmissionService
)

router = APIRouter(prefix="/api/v1/lenders", tags=["Lender Comparison & Submission"])


@router.get("/", response_model=List[LenderResponse], summary="List Active Lenders")
async def list_lenders(
    lender_type: Optional[str] = Query(None, description="Filter by lender type"),
    is_active: bool = Query(True, description="Only show active lenders"),
    db: AsyncSession = Depends(get_async_session)
) -> List[LenderResponse]:
    """List all active lenders with optional filtering."""
    try:
        service = LenderComparisonService(db)
        lenders = await service.list_active_lenders(lender_type)
        return [LenderResponse.model_validate(lender) for lender in lenders]
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "error_code": "VALIDATION_ERROR"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"})


@router.get("/{lender_id}/products", response_model=List[LenderProductResponse], summary="Get Lender Products")
async def get_lender_products(
    lender_id: int,
    mortgage_type: Optional[str] = Query(None, description="Filter by mortgage type"),
    is_active: bool = Query(True, description="Only show active products"),
    db: AsyncSession = Depends(get_async_session)
) -> List[LenderProductResponse]:
    """Retrieve all active products for a specific lender."""
    try:
        if lender_id <= 0:
            raise HTTPException(status_code=400, detail={"error": "Invalid lender ID", "error_code": "INVALID_ID"})
        service = LenderComparisonService(db)
        products = await service.get_lender_products(lender_id, mortgage_type)
        return [LenderProductResponse.model_validate(p) for p in products]
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "error_code": "VALIDATION_ERROR"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"})


@router.post("/match", response_model=LenderMatchResponse, summary="Match Lenders to Application")
async def match_lenders(
    payload: LenderMatchRequest,
    db: AsyncSession = Depends(get_async_session)
) -> LenderMatchResponse:
    """Match lenders based on application criteria."""
    try:
        service = LenderComparisonService(db)
        return await service.match_lenders_to_application(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "error_code": "VALIDATION_ERROR"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"})


# Submission Routes

submission_router = APIRouter(prefix="/api/v1/applications", tags=["Lender Submissions"])


@submission_router.post("/{application_id}/submissions", response_model=LenderSubmissionResponse, status_code=status.HTTP_201_CREATED, summary="Create Lender Submission")
async def create_submission(
    application_id: int,
    payload: LenderSubmissionCreate,
    db: AsyncSession = Depends(get_async_session)
) -> LenderSubmissionResponse:
    """Create a new lender submission record."""
    try:
        if application_id != payload.application_id:
            raise HTTPException(status_code=400, detail={"error": "Application ID mismatch", "error_code": "ID_MISMATCH"})
        service = LenderSubmissionService(db)
        return await service.create_submission(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "error_code": "VALIDATION_ERROR"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"})


@submission_router.get("/{application_id}/submissions", response_model=List[LenderSubmissionResponse], summary="List Lender Submissions")
async def list_submissions(
    application_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> List[LenderSubmissionResponse]:
    """List all submissions for an application."""
    try:
        service = LenderSubmissionService(db)
        return await service.list_submissions_for_application(application_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "error_code": "VALIDATION_ERROR"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"})


@submission_router.put("/{application_id}/submissions/{submission_id}", response_model=LenderSubmissionResponse, summary="Update Lender Submission Status")
async def update_submission(
    application_id: int,
    submission_id: int,
    payload: LenderSubmissionUpdate,
    db: AsyncSession = Depends(get_async_session)
) -> LenderSubmissionResponse:
    """Update the status of a lender submission."""
    try:
        service = LenderSubmissionService(db)
        return await service.update_submission_status(submission_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "error_code": "VALIDATION_ERROR"})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e), "error_code": "INTERNAL_ERROR"})