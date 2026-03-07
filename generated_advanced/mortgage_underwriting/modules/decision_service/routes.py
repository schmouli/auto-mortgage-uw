from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.decision_service.schemas import (

    DecisionEvaluateRequest, DecisionEvaluateResponse,
    DecisionResponse, DecisionAuditTrailResponse
)
from mortgage_underwriting.modules.decision_service.services import DecisionService

router = APIRouter(prefix="/api/v1/decision", tags=["Underwriting Decisions"])


@router.post("/evaluate", response_model=DecisionEvaluateResponse, status_code=status.HTTP_201_CREATED)
async def evaluate_decision(
    payload: DecisionEvaluateRequest,
    db: AsyncSession = Depends(get_async_session),
):
    """Run underwriting decision evaluation.
    
    Requires authenticated access with underwriter or system role.
    """
    try:
        service = DecisionService(db)
        return await service.evaluate(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "error_code": "DECISION_EVALUATION_FAILED"}
        )


@router.get("/{application_id}", response_model=DecisionResponse)
async def get_decision(
    application_id: UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Retrieve a previously calculated decision record."""
    try:
        service = DecisionService(db)
        decision = await service.get_decision(application_id)
        return decision
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": str(e), "error_code": "DECISION_NOT_FOUND"}
        )


@router.get("/{application_id}/audit", response_model=DecisionAuditTrailResponse)
async def get_decision_audit(
    application_id: UUID,
    db: AsyncSession = Depends(get_async_session),
):
    """Get full audit trail for a decision including all rules evaluated."""
    try:
        service = DecisionService(db)
        audit_trail = await service.get_audit_trail(application_id)
        return DecisionAuditTrailResponse(audit_trail=audit_trail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": str(e), "error_code": "AUDIT_TRAIL_NOT_FOUND"}
        )