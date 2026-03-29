from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.decision.schemas import (
    DecisionEvaluateRequest,
    DecisionEvaluateResponse,
    DecisionRecordResponse
)
from mortgage_underwriting.modules.decision.services import DecisionService

router = APIRouter(prefix="/api/v1/decision", tags=["Decision Engine"])


def get_decision_service(db: AsyncSession = Depends(get_async_session)) -> DecisionService:
    return DecisionService(db)


@router.post("/evaluate", 
          response_model=DecisionEvaluateResponse, 
          status_code=status.HTTP_201_CREATED,
          summary="Run underwriting decision")
async def evaluate_decision(
    payload: DecisionEvaluateRequest,
    service: Annotated[DecisionService, Depends(get_decision_service)]
) -> DecisionEvaluateResponse:
    """Execute deterministic underwriting decision engine.
    
    Takes borrower, property and loan data to produce an underwriting decision
    following OSFI B-20 guidelines.
    """
    try:
        return await service.evaluate(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "DECISION_EVAL_ERROR", "message": str(e)}
        )


@router.get("/{application_id}", 
         response_model=DecisionRecordResponse,
         summary="Retrieve decision record")
async def get_decision_record(
    application_id: UUID,
    service: Annotated[DecisionService, Depends(get_decision_service)]
) -> DecisionRecordResponse:
    """Get previously calculated decision record."""
    try:
        record = await service.get_decision(application_id)
        return record
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "DECISION_NOT_FOUND", "message": str(e)}
        )


@router.get("/{application_id}/audit", 
         summary="Get audit trail")
async def get_audit_trail(
    application_id: UUID,
    service: Annotated[DecisionService, Depends(get_decision_service)]
) -> dict:
    """Get full audit trail for compliance purposes."""
    try:
        return await service.get_audit_trail(application_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "AUDIT_TRAIL_NOT_FOUND", "message": str(e)}
        )