from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.underwriting.schemas import (
    UnderwritingCalculationRequest,
    UnderwritingEvaluationRequest,
    UnderwritingResultResponse,
    UnderwritingResultBase,
    UnderwritingOverrideCreate,
    UnderwritingOverrideResponse
)
from mortgage_underwriting.modules.underwriting.services import UnderwritingService

router = APIRouter(prefix="/api/v1/underwriting", tags=["Underwriting Engine"])

@router.post("/calculate", response_model=UnderwritingResultBase)
async def calculate_qualification(
    payload: UnderwritingCalculationRequest,
    db: AsyncSession = Depends(get_async_session)
) -> UnderwritingResultBase:
    """Run qualification calculations without persisting results (what-if scenario)."""
    try:
        service = UnderwritingService(db)
        return await service.calculate_qualification(payload)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "error_code": "CALCULATION_ERROR"}
        )

@router.post("/applications/{application_id}/evaluate", response_model=UnderwritingResultResponse)
async def evaluate_application(
    application_id: int,
    payload: UnderwritingEvaluationRequest,
    db: AsyncSession = Depends(get_async_session)
) -> UnderwritingResultResponse:
    """Evaluate an application and save the underwriting result."""
    try:
        service = UnderwritingService(db)
        result = await service.evaluate_and_save(payload, application_id)
        return UnderwritingResultResponse.model_validate(result)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "error_code": "EVALUATION_ERROR"}
        )

@router.get("/applications/{result_id}/result", response_model=UnderwritingResultResponse)
async def get_underwriting_result(
    result_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> UnderwritingResultResponse:
    """Get a saved underwriting result."""
    service = UnderwritingService(db)
    result = await service.get_result(result_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Underwriting result not found", "error_code": "RESULT_NOT_FOUND"}
        )
        
    return UnderwritingResultResponse.model_validate(result)

@router.post("/applications/{result_id}/override", response_model=UnderwritingOverrideResponse)
async def create_override(
    result_id: int,
    payload: UnderwritingOverrideCreate,
    request: Request,
    db: AsyncSession = Depends(get_async_session)
) -> UnderwritingOverrideResponse:
    """Create an admin override for an underwriting result."""
    try:
        # Extract user ID from request (would come from auth middleware in real implementation)
        user_id = getattr(request.state, 'user_id', None)
        
        service = UnderwritingService(db)
        override_payload = UnderwritingOverrideCreate(
            result_id=result_id,
            reason=payload.reason,
            approved=payload.approved
        )
        return await service.create_override(override_payload, user_id)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "error_code": "OVERRIDE_ERROR"}
        )