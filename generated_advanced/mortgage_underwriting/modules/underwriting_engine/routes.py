```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.api import deps
from app.underwriting import services, schemas

router = APIRouter(prefix="/underwriting", tags=["underwriting"])

@router.post("/calculate", response_model=schemas.UnderwritingCalculateResponse)
async def calculate_qualification(
    *,
    db: AsyncSession = Depends(deps.get_db),
    input_data: schemas.UnderwritingCalculateRequest
):
    """
    Run underwriting qualification calculation without saving results.
    
    This endpoint performs a complete underwriting analysis based on provided financial data
    but does not persist the results. It's useful for pre-qualification checks.
    """
    try:
        result = await services.UnderwritingService.run_underwriting(db, input_data)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Calculation failed: {str(e)}"
        )

@router.post("/applications/{application_id}/evaluate", response_model=schemas.UnderwritingResultResponse)
async def evaluate_application(
    *,
    db: AsyncSession = Depends(deps.get_db),
    application_id: str,
    input_data: schemas.UnderwritingEvaluateRequest
):
    """
    Evaluate an application and save the underwriting results.
    
    This endpoint runs a complete underwriting analysis and saves the results
    associated with the given application ID. If no record exists, it will be created.
    """
    try:
        result = await services.UnderwritingService.evaluate_and_save(
            db, application_id, input_data, input_data.changed_by
        )
        return {
            "id": uuid.uuid4().int & 0x7FFFFFFF,  # Simplified ID generation
            "application_id": application_id,
            **result.dict()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {str(e)}"
        )

@router.get("/applications/{application_id}/result", response_model=schemas.UnderwritingResultResponse)
async def get_evaluation_result(
    *,
    db: AsyncSession = Depends(deps.get_db),
    application_id: str
):
    """
    Retrieve saved underwriting result for an application.
    
    Returns the previously saved underwriting decision and calculations
    for the specified application ID.
    """
    try:
        result = await services.UnderwritingService.get_result(db, application_id)
        return {
            "id": uuid.uuid4().int & 0x7FFFFFFF,  # Simplified ID generation
            "application_id": application_id,
            **result.dict()
        }
    except services.ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve result: {str(e)}"
        )

@router.post("/applications/{application_id}/override", status_code=status.HTTP_204_NO_CONTENT)
async def override_decision(
    *,
    db: AsyncSession = Depends(deps.get_db),
    application_id: str,
    override_data: schemas.OverrideCreate,
    current_user = Depends(deps.get_current_active_admin)  # Assuming you have admin dependency
):
    """
    Create an administrative override for an underwriting decision.
    
    Only administrators can perform overrides. A reason must be provided
    explaining why the override is necessary.
    """
    try:
        await services.UnderwritingService.create_override(
            db, application_id, override_data.dict(), current_user.role
        )
    except services.ApplicationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except services.InvalidOverrideError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Override failed: {str(e)}"
        )
```