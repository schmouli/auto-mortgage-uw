from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.underwriting.schemas import (
from mortgage_underwriting.modules.underwriting.services import UnderwritingService

    UnderwritingCalculationRequest,
    UnderwritingEvaluationRequest,
    UnderwritingCalculationResponse,
    UnderwritingResultResponse,
    OverrideRequest,
    OverrideResponse
)

router = APIRouter(prefix="/api/v1/underwriting", tags=["Underwriting Engine"])

# Dependency for getting current user ID (stub - replace with actual auth)


async def get_current_user_id(request: Request) -> int:
    # This would normally extract user ID from JWT token or session
    # For now, returning a placeholder
    return 1

CurrentUser = Annotated[int, Depends(get_current_user_id)]


def get_underwriting_service(db: AsyncSession = Depends(get_async_session)) -> UnderwritingService:
    return UnderwritingService(db)

UnderwritingServiceDep = Annotated[UnderwritingService, Depends(get_underwriting_service)]


@router.post("/calculate", response_model=UnderwritingCalculationResponse)


async def calculate_underwriting(
    payload: UnderwritingCalculationRequest,
    service: UnderwritingServiceDep
) -> UnderwritingCalculationResponse:
    """Run qualification calculations without persisting results.
    
    Performs stress testing per OSFI B-20 regulations and calculates
    GDS/TDS ratios with CMHC insurance requirements.
    """
    try:
        return await service.calculate_qualification(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": str(e) if hasattr(e, '__str__') else "Invalid request data",
                "error_code": getattr(e, 'error_code', 'CALCULATION_ERROR')
            }
        )


@router.post("/applications/{application_id}/evaluate", response_model=UnderwritingResultResponse, status_code=status.HTTP_201_CREATED)


async def evaluate_underwriting(
    application_id: int,
    payload: UnderwritingEvaluationRequest,
    service: UnderwritingServiceDep,
    user_id: CurrentUser
) -> UnderwritingResultResponse:
    """Evaluate underwriting criteria and save the result.
    
    Requires authentication and links result to specific application.
    """
    try:
        # Ensure application_id matches payload if provided
        if payload.application_id and payload.application_id != application_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Application ID mismatch between path and body",
                    "error_code": "APPLICATION_ID_MISMATCH"
                }
            )
        
        # Set application_id in payload if not already set
        payload.application_id = application_id
        
        return await service.evaluate_and_save(payload, user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": str(e) if hasattr(e, '__str__') else "Failed to evaluate underwriting",
                "error_code": getattr(e, 'error_code', 'EVALUATION_ERROR')
            }
        )


@router.get("/applications/{application_id}/result", response_model=UnderwritingResultResponse)


async def get_underwriting_result(
    application_id: int,
    service: UnderwritingServiceDep
) -> UnderwritingResultResponse:
    """Get the most recent saved underwriting result for an application.
    
    Retrieves latest underwriting decision for compliance auditing.
    """
    # Find the most recent underwriting result for this application
    # In practice, you might want to pass result_id directly
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Endpoint requires implementation to fetch by application ID",
            "error_code": "NOT_IMPLEMENTED"
        }
    )


@router.get("/results/{result_id}", response_model=UnderwritingResultResponse)


async def get_underwriting_result_by_id(
    result_id: int,
    service: UnderwritingServiceDep
) -> UnderwritingResultResponse:
    """Get a saved underwriting result by its ID.
    
    Used for retrieving historical underwriting decisions.
    """
    try:
        return await service.get_result(result_id)
    except Exception as e:
        raise HTTPException(
            status_code=getattr(e, 'status_code', status.HTTP_400_BAD_REQUEST),
            detail={
                "message": str(e) if hasattr(e, '__str__') else "Failed to retrieve result",
                "error_code": getattr(e, 'error_code', 'RETRIEVAL_ERROR')
            }
        )


@router.post("/results/{result_id}/override", response_model=OverrideResponse, status_code=status.HTTP_201_CREATED)


async def create_underwriting_override(
    result_id: int,
    payload: OverrideRequest,
    service: UnderwritingServiceDep,
    user_id: CurrentUser
) -> OverrideResponse:
    """Create an admin override for an underwriting result.
    
    Only authorized users can perform overrides with documented reasons.
    """
    try:
        return await service.create_override(result_id, payload, user_id)
    except Exception as e:
        raise HTTPException(
            status_code=getattr(e, 'status_code', status.HTTP_400_BAD_REQUEST),
            detail={
                "message": str(e) if hasattr(e, '__str__') else "Failed to create override",
                "error_code": getattr(e, 'error_code', 'OVERRIDE_ERROR')
            }
        )