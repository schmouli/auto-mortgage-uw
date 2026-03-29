from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.policy.schemas import (
    LenderPolicyCreate,
    LenderPolicyUpdate,
    LenderPolicyResponse,
    PolicyEvaluationRequest,
    PolicyEvaluationResponse,
    PolicyListResponse
)
from mortgage_underwriting.modules.policy.services import PolicyService
from mortgage_underwriting.modules.policy.exceptions import PolicyNotFoundError, InvalidXMLFormatError

router = APIRouter(prefix="/api/v1/policy", tags=["Policy Management"])


def get_policy_service(db: AsyncSession = Depends(get_async_session)) -> PolicyService:
    return PolicyService(db)


@router.get("/lenders", response_model=PolicyListResponse)
async def list_lender_policies(
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    size: int = Query(50, ge=1, le=100, description="Number of items per page (max 100)"),
    service: PolicyService = Depends(get_policy_service)
):
    """List all active lender policies with pagination."""
    try:
        policies, total = await service.get_all_policies(page, size)
        return PolicyListResponse(
            items=[LenderPolicyResponse.model_validate(p) for p in policies],
            total=total,
            page=page,
            size=size
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to fetch policies", "error_code": "POLICY_FETCH_ERROR"}
        )


@router.get("/{policy_id}", response_model=LenderPolicyResponse)
async def get_lender_policy(
    policy_id: int,
    service: PolicyService = Depends(get_policy_service)
):
    """Get a specific lender policy by ID."""
    try:
        policy = await service.get_policy_by_id(policy_id)
        if not policy:
            raise PolicyNotFoundError(f"Policy with ID {policy_id} not found.")
        return LenderPolicyResponse.model_validate(policy)
    except PolicyNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": str(e), "error_code": "POLICY_NOT_FOUND"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to fetch policy", "error_code": "POLICY_FETCH_ERROR"}
        )


@router.post("/", response_model=LenderPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_lender_policy(
    payload: LenderPolicyCreate,
    service: PolicyService = Depends(get_policy_service)
):
    """Create a new lender policy from XML content."""
    try:
        policy = await service.create_policy(payload)
        return LenderPolicyResponse.model_validate(policy)
    except InvalidXMLFormatError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "error_code": "INVALID_XML_FORMAT"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to create policy", "error_code": "POLICY_CREATE_ERROR"}
        )


@router.put("/{policy_id}", response_model=LenderPolicyResponse)
async def update_lender_policy(
    policy_id: int,
    payload: LenderPolicyUpdate,
    service: PolicyService = Depends(get_policy_service)
):
    """Update an existing lender policy's XML content."""
    try:
        policy = await service.update_policy(policy_id, payload)
        return LenderPolicyResponse.model_validate(policy)
    except PolicyNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": str(e), "error_code": "POLICY_NOT_FOUND"}
        )
    except InvalidXMLFormatError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(e), "error_code": "INVALID_XML_FORMAT"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to update policy", "error_code": "POLICY_UPDATE_ERROR"}
        )


@router.post("/evaluate", response_model=PolicyEvaluationResponse)
async def evaluate_application_against_policy(
    payload: PolicyEvaluationRequest,
    service: PolicyService = Depends(get_policy_service)
):
    """Evaluate application data against a specific policy."""
    try:
        result = await service.evaluate_policy(payload)
        return result
    except PolicyNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": str(e), "error_code": "POLICY_NOT_FOUND"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to evaluate policy", "error_code": "POLICY_EVALUATION_ERROR"}
        )