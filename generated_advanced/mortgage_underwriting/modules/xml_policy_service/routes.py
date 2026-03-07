from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.policy_xml.schemas import (
from mortgage_underwriting.modules.policy_xml.services import PolicyXMLService

    LenderPolicyResponse,
    PolicyListResponse,
    LenderPolicyCreate,
    LenderPolicyUpdate,
    PolicyEvaluationRequest,
    PolicyEvaluationResponse
)
from mortgage_underwriting.modules.policy_xml.exceptions import PolicyNotFoundError, InvalidPolicyXMLError

router = APIRouter(prefix="/api/v1/policy", tags=["Policy Management"])

@router.get("/lenders", response_model=PolicyListResponse)
async def list_lender_policies(
    status: Optional[str] = Query(None, description="Filter by policy status"),
    limit: int = Query(50, ge=1, le=200, description="Pagination limit"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_async_session)
):
    """List all loaded lender policies with metadata."""
    service = PolicyXMLService(db)
    return await service.list_policies(status=status, limit=limit, offset=offset)

@router.get("/{lender_id}", response_model=LenderPolicyResponse)
async def get_lender_policy(
    lender_id: str,
    version: Optional[str] = Query(None, description="Specific policy version"),
    db: AsyncSession = Depends(get_async_session)
):
    """Get specific lender policy including parsed XML content."""
    service = PolicyXMLService(db)
    try:
        return await service.get_policy(lender_id, version)
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/", response_model=LenderPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_lender_policy(
    payload: LenderPolicyCreate,
    db: AsyncSession = Depends(get_async_session)
):
    """Create a new lender policy from XML content."""
    service = PolicyXMLService(db)
    try:
        return await service.create_policy(payload)
    except InvalidPolicyXMLError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/{lender_id}", response_model=LenderPolicyResponse)
async def update_lender_policy(
    lender_id: str,
    payload: LenderPolicyUpdate,
    db: AsyncSession = Depends(get_async_session)
):
    """Update an existing lender policy."""
    service = PolicyXMLService(db)
    try:
        return await service.update_policy(lender_id, payload)
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidPolicyXMLError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/evaluate", response_model=PolicyEvaluationResponse)
async def evaluate_application_against_policy(
    request: PolicyEvaluationRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """Evaluate application data against specified lender policy."""
    service = PolicyXMLService(db)
    try:
        return await service.evaluate_policy(request)
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidPolicyXMLError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))