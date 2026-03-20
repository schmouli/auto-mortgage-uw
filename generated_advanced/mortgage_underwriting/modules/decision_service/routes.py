from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.decision.schemas import (

    DecisionEvaluateRequest,
    DecisionResponse,
    DecisionRetrieveResponse,
    AuditTrailResponse,
    DecisionListResponse
)
from mortgage_underwriting.modules.decision.services import DecisionService

router = APIRouter(prefix="/api/v1/decision", tags=["Underwriting Decisions"])

@router.post("/evaluate", response_model=DecisionResponse, status_code=status.HTTP_201_CREATED)


async def evaluate_decision(
    payload: DecisionEvaluateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> DecisionResponse:
    """Evaluate a mortgage application and return underwriting decision.
    
    Complies with OSFI B-20 stress testing, CMHC insurance logic,
    and FINTRAC audit requirements.
    """
    service = DecisionService(db)
    try:
        return await service.evaluate(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "error_code": "DECISION_EVALUATION_FAILED"}
        )

@router.get("/{application_id}", response_model=DecisionRetrieveResponse)


async def get_decision(
    application_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> DecisionRetrieveResponse:
    """Retrieve a specific underwriting decision by application ID."""
    service = DecisionService(db)
    try:
        return await service.get_decision(application_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": str(e), "error_code": "DECISION_NOT_FOUND"}
        )

@router.get("/{application_id}/audit", response_model=list[AuditTrailResponse])


async def get_decision_audit(
    application_id: UUID,
    db: AsyncSession = Depends(get_async_session),
) -> list[AuditTrailResponse]:
    """Get full audit trail for a decision including all calculation steps."""
    service = DecisionService(db)
    try:
        return await service.get_audit_trail(application_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": str(e), "error_code": "AUDIT_TRAIL_NOT_FOUND"}
        )