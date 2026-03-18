from typing import Optional
import structlog

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.policy.schemas import (
    LenderPolicyListResponse,
    LenderPolicyDetail,
    PolicyEvaluationRequest,
    PolicyEvaluationResponse,
    PolicyUpdateRequest
)
from mortgage_underwriting.modules.policy.services import PolicyService
from mortgage_underwriting.modules.policy.exceptions import PolicyNotFoundException, PolicyValidationError

router = APIRouter(prefix="/api/v1/policy", tags=["XML Policy Management"])
logger = structlog.get_logger()


@router.get("/lenders", response_model=LenderPolicyListResponse)
async def list_lender_policies(
    page: int = Query(1, ge=1),
    size: int = Query(50, le=100),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_async_session)
) -> LenderPolicyListResponse:
    """List all loaded lender policies with pagination."""
    service = PolicyService(db)
    return await service.list_policies(page=page, size=size, is_active=is_active)


@router.get("/{lender_id}", response_model=LenderPolicyDetail)
async def get_lender_policy(
    lender_id: str,
    db: AsyncSession = Depends(get_async_session)
) -> LenderPolicyDetail:
    """Get detailed policy configuration for a specific lender."""
    service = PolicyService(db)
    try:
        return await service.get_policy(lender_id)
    except PolicyNotFoundException as e:
        logger.error("policy_not_found", lender_id=lender_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "POLICY_001"}
        )


@router.put("/{lender_id}", response_model=LenderPolicyDetail)
async def update_lender_policy(
    lender_id: str,
    payload: PolicyUpdateRequest,
    db: AsyncSession = Depends(get_async_session)
) -> LenderPolicyDetail:
    """Update or create lender policy from XML content."""
    service = PolicyService(db)
    try:
        return await service.update_policy(lender_id, payload)
    except PolicyValidationError as e:
        logger.error("policy_validation_error", lender_id=lender_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "POLICY_002"}
        )
    except Exception as e:
        logger.error("unexpected_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Internal server error", "error_code": "POLICY_003"}
        )


@router.post("/evaluate", response_model=PolicyEvaluationResponse)
async def evaluate_application_against_policy(
    request: PolicyEvaluationRequest,
    db: AsyncSession = Depends(get_async_session)
) -> PolicyEvaluationResponse:
    """Evaluate an application against a lender's policy rules."""
    service = PolicyService(db)
    try:
        return await service.evaluate_policy(request)
    except PolicyNotFoundException as e:
        logger.error("policy_not_found_for_evaluation", lender_id=request.lender_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "EVALUATION_001"}
        )
    except ValueError as e:
        logger.error("evaluation_value_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "EVALUATION_002"}
        )
    except Exception as e:
        logger.error("unexpected_evaluation_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": "Internal server error during evaluation", "error_code": "EVALUATION_003"}
        )