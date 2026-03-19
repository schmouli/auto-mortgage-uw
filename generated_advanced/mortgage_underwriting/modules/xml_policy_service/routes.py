from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.xml_policy_service.schemas import (
from mortgage_underwriting.modules.xml_policy_service.services import XmlPolicyService

    LenderPolicySummary,
    LenderPolicyDetail,
    LenderPolicyCreate,
    LenderPolicyUpdate
)

router = APIRouter(prefix="/api/v1/policy", tags=["XML Policy Service"])


def get_current_user_hash() -> str:
    # In a real implementation, this would extract user hash from auth token
    return "mock-user-hash"


@router.get("/lenders", response_model=List[LenderPolicySummary])


async def list_lender_policies(
    limit: int = Query(100, le=100, ge=1),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session)
):
    """List all active lender policies with pagination."""
    service = XmlPolicyService(db)
    return await service.list_policies(limit=limit, offset=offset)


@router.get("/{lender_id}", response_model=LenderPolicyDetail)


async def get_lender_policy(
    lender_id: str,
    db: AsyncSession = Depends(get_async_session)
):
    """Get detailed information for a specific lender policy."""
    service = XmlPolicyService(db)
    policy = await service.get_policy(lender_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.post("/", response_model=LenderPolicyDetail, status_code=status.HTTP_201_CREATED)


async def create_lender_policy(
    payload: LenderPolicyCreate,
    db: AsyncSession = Depends(get_async_session),
    user_hash: str = Depends(get_current_user_hash)
):
    """Create a new lender policy from XML content."""
    service = XmlPolicyService(db)
    try:
        return await service.create_policy(payload, user_hash)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{lender_id}", response_model=LenderPolicyDetail)


async def update_lender_policy(
    lender_id: str,
    payload: LenderPolicyUpdate,
    db: AsyncSession = Depends(get_async_session),
    user_hash: str = Depends(get_current_user_hash)
):
    """Update an existing lender policy."""
    service = XmlPolicyService(db)
    policy = await service.update_policy(lender_id, payload, user_hash)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.post("/evaluate", response_model=dict)


async def evaluate_application_against_policy(
    lender_id: str,
    application_data: dict,
    db: AsyncSession = Depends(get_async_session)
):
    """Evaluate a mortgage application against a specific lender's policy."""
    service = XmlPolicyService(db)
    try:
        return await service.evaluate_policy(lender_id, application_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))