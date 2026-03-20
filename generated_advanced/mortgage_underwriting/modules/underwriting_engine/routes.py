from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.underwriting.schemas import (
    UnderwritingCalculateRequest,
    UnderwritingResultCreate,
    UnderwritingResultUpdate,
    UnderwritingResultResponse
)
from mortgage_underwriting.modules.underwriting.services import UnderwritingService
from mortgage_underwriting.modules.underwriting.models import UnderwritingResult

router = APIRouter(prefix="/api/v1/underwriting", tags=["Underwriting Engine"])


@router.post("/calculate", response_model=UnderwritingResultResponse)
async def calculate_qualification(
    payload: UnderwritingCalculateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> UnderwritingResultResponse:
    """Run qualification calculation without saving."""
    service = UnderwritingService(db)
    try:
        result = service.calculate_qualification(payload)
        return UnderwritingResultResponse(**result)
    except AppException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": getattr(e, 'error_code', 'CALCULATION_ERROR')}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"}
        )


@router.post("/applications/{application_id}/evaluate", response_model=UnderwritingResultResponse, status_code=status.HTTP_201_CREATED)
async def evaluate_application(
    application_id: int,
    client_id: int,
    payload: UnderwritingCalculateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> UnderwritingResultResponse:
    """Evaluate application and save underwriting result."""
    service = UnderwritingService(db)
    try:
        result = await service.evaluate_and_save(application_id, client_id, payload)
        return result
    except AppException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": getattr(e, 'error_code', 'EVALUATION_ERROR')}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"}
        )


@router.get("/applications/{application_id}/result", response_model=UnderwritingResultResponse)
async def get_underwriting_result(
    application_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> UnderwritingResultResponse:
    """Get saved underwriting result for an application."""
    service = UnderwritingService(db)
    stmt = select(UnderwritingResult).where(UnderwritingResult.application_id == application_id)
    result = await db.execute(stmt)
    instance = result.scalar_one_or_none()
    
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Underwriting result not found", "error_code": "RESULT_NOT_FOUND"}
        )
    return instance


@router.post("/applications/{application_id}/override", response_model=UnderwritingResultResponse)
async def override_underwriting_result(
    application_id: int,
    payload: UnderwritingResultUpdate,
    db: AsyncSession = Depends(get_async_session),
) -> UnderwritingResultResponse:
    """Apply admin override to underwriting result."""
    service = UnderwritingService(db)
    
    # Get the current result
    stmt = select(UnderwritingResult).where(UnderwritingResult.application_id == application_id)
    result_query = await db.execute(stmt)
    instance = result_query.scalar_one_or_none()
    
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Underwriting result not found", "error_code": "RESULT_NOT_FOUND"}
        )
        
    try:
        updated = await service.apply_override(instance.id, payload)
        return updated
    except AppException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": getattr(e, 'error_code', 'OVERRIDE_ERROR')}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"}
        )