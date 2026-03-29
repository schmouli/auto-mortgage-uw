from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import (
from fastapi import APIRouter, Depends, HTTPException, status

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.auth.dependencies import get_current_active_user
from mortgage_underwriting.modules.users.models import User

    UnderwritingCalculationRequest,
    UnderwritingEvaluationRequest,
    UnderwritingOverrideRequest,
    UnderwritingCalculationResponse,
    UnderwritingResultResponse,
    UnderwritingOverrideResponse
)
from .services import UnderwritingService

router = APIRouter(prefix="/api/v1/underwriting", tags=["Underwriting Engine"])


def get_underwriting_service(db: AsyncSession = Depends(get_async_session)) -> UnderwritingService:
    return UnderwritingService(db)


@router.post("/calculate", response_model=UnderwritingCalculationResponse)


async def calculate_qualification(
    request: UnderwritingCalculationRequest,
    service: UnderwritingService = Depends(get_underwriting_service)
) -> UnderwritingCalculationResponse:
    """Run qualification calculation without saving results."""
    try:
        return await service.calculate(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "error_code": "CALCULATION_ERROR"}
        )


@router.post("/applications/{application_id}/evaluate", response_model=UnderwritingResultResponse)


async def evaluate_application(
    application_id: int,
    request: UnderwritingEvaluationRequest,
    current_user: User = Depends(get_current_active_user),
    service: UnderwritingService = Depends(get_underwriting_service)
) -> UnderwritingResultResponse:
    """Evaluate application and save underwriting result."""
    try:
        # Set application_id in request
        request.application_id = application_id
        return await service.evaluate(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "error_code": "EVALUATION_ERROR"}
        )


@router.get("/applications/{application_id}/result", response_model=UnderwritingResultResponse)


async def get_evaluation_result(
    application_id: int,
    current_user: User = Depends(get_current_active_user),
    service: UnderwritingService = Depends(get_underwriting_service)
) -> UnderwritingResultResponse:
    """Get saved underwriting result for application."""
    try:
        # Find result by application_id
        from .models import UnderwritingResult
        from sqlalchemy import select
        stmt = select(UnderwritingResult).where(UnderwritingResult.application_id == application_id)
        result = await service.db.scalar(stmt)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": f"No underwriting result found for application {application_id}", "error_code": "RESULT_NOT_FOUND"}
            )
            
        return UnderwritingResultResponse.model_validate(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "error_code": "RETRIEVAL_ERROR"}
        )


@router.post("/applications/{application_id}/override", response_model=UnderwritingOverrideResponse)


async def create_admin_override(
    application_id: int,
    request: UnderwritingOverrideRequest,
    current_user: User = Depends(get_current_active_user),
    service: UnderwritingService = Depends(get_underwriting_service)
) -> UnderwritingOverrideResponse:
    """Create admin override for underwriting result."""
    try:
        # Find result by application_id
        from .models import UnderwritingResult
        from sqlalchemy import select
        stmt = select(UnderwritingResult).where(UnderwritingResult.application_id == application_id)
        result = await service.db.scalar(stmt)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": f"No underwriting result found for application {application_id}", "error_code": "RESULT_NOT_FOUND"}
            )
            
        return await service.create_override(result.id, current_user.id, request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "error_code": "OVERRIDE_ERROR"}
        )