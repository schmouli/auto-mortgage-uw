```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.decision.models import DecisionAudit
from mortgage_underwriting.modules.decision.schemas import (
    DecisionAuditCreate, 
    DecisionAuditResponse,
    DecisionHistoryQueryParams
)
from mortgage_underwriting.modules.decision.services import DecisionService

router = APIRouter(prefix="/api/v1/decisions", tags=["Decision Auditing"])

@router.get("/history/{application_id}", response_model=List[DecisionAuditResponse])
async def get_decision_history(
    application_id: int,
    query_params: DecisionHistoryQueryParams = Depends(),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Get paginated decision history for a mortgage application.
    
    Args:
        application_id: ID of the mortgage application
        query_params: Query parameters including skip and limit
        
    Returns:
        Paginated list of decision audits
        
    FIXED: Now properly implements pagination with skip/limit parameters
    """
    service = DecisionService(db)
    return await service.get_decision_history(application_id, query_params)

@router.post("/", response_model=DecisionAuditResponse, status_code=status.HTTP_201_CREATED)
async def create_decision_audit(
    payload: DecisionAuditCreate,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Create a new decision audit record.
    
    Args:
        payload: Decision audit creation data
        
    Returns:
        Created decision audit object
    """
    service = DecisionService(db)
    instance = DecisionAudit(**payload.model_dump())
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    return instance
```