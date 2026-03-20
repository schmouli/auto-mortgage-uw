from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.policy.schemas import (
    LenderPolicyCreate,
    LenderPolicyUpdate,
    LenderPolicyResponse,
    PolicyEvaluateRequest,
    PolicyEvaluateResponse,
    PolicyListResponse
)
from mortgage_underwriting.modules.policy.services import XMLPolicyService, NotFoundError

router = APIRouter(prefix="/api/v1/policy", tags=["XML Policy Service"])

PageSize = Annotated[int, Query(ge=1, le=100, description="Number of items per page")]
PageNumber = Annotated[int, Query(ge=1, description="Page number (1-indexed)")]


@router.get("/lenders", response_model=PolicyListResponse)
async def list_lender_policies(
    page: PageNumber = 1,
    size: PageSize = 50,
    db: AsyncSession = Depends(get_async_session),
) -> PolicyListResponse:
    """List all loaded lender policies with pagination."""
    service = XMLPolicyService(db)
    policies, total = await service.list_policies(page=page, size=size)
    
    return PolicyListResponse(
        items=policies,
        total=total,
        page=page,
        size=size
    )


@router.get("/{lender_id}", response_model=LenderPolicyResponse)
async def get_lender_policy(
    lender_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> LenderPolicyResponse:
    """Get specific lender policy."""
    service = XMLPolicyService(db)
    try:
        return await service.get_policy(lender_id)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "POLICY_NOT_FOUND", "message": str(e)}
        )


@router.put("/{lender_id}", response_model=LenderPolicyResponse)
async def update_lender_policy(
    lender_id: str,
    payload: LenderPolicyUpdate,
    db: AsyncSession = Depends(get_async_session),
) -> LenderPolicyResponse:
    """Update lender policy XML."""
    service = XMLPolicyService(db)
    try:
        return await service.create_or_update_policy(lender_id, payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "POLICY_UPDATE_FAILED", "message": str(e)}
        )


@router.post("/evaluate", response_model=PolicyEvaluateResponse)
async def evaluate_application_against_policy(
    request: PolicyEvaluateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> PolicyEvaluateResponse:
    """Evaluate application data against policy."""
    service = XMLPolicyService(db)
    try:
        return await service.evaluate_policy(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "EVALUATION_FAILED", "message": str(e)}
        )