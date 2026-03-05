from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import structlog

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.underwriting_engine import services, schemas

router = APIRouter(prefix="/api/v1/underwriting", tags=["Underwriting Engine"])
logger = structlog.get_logger()


@router.post("/calculate", response_model=schemas.UnderwritingCalculateResponse)
async def calculate_qualification(
    *,
    db: AsyncSession = Depends(get_async_session),
    input_data: schemas.UnderwritingCalculateRequest
):
    """
    Run underwriting qualification calculation without saving results.
    
    This endpoint performs a complete underwriting analysis based on provided financial data
    but does not persist the results. It's useful for pre-qualification checks.
    """
    try:
        # FIXED: Replaced generic except with specific exception handling
        service = services.UnderwritingService(db)
        result = await service.run_underwriting(input_data)
        return result
    except ValueError as e:
        logger.warning("invalid_input_for_calculation", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input data: {str(e)}"
        )
    except Exception as e:
        # FIXED: Added context logging for exceptions
        logger.error("calculation_failed", error=str(e), input_data=input_data.dict())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": f"Calculation failed: {str(e)}", "error_code": "CALCULATION_ERROR"}
        )


@router.post("/applications/{application_id}/evaluate", response_model=schemas.UnderwritingResultResponse)
async def evaluate_application(
    *,
    db: AsyncSession = Depends(get_async_session),
    application_id: str,
    input_data: schemas.UnderwritingEvaluateRequest
):
    """
    Evaluate an application and save the underwriting results.
    
    This endpoint runs a complete underwriting analysis and saves the results
    associated with the given application ID. If no record exists, it will be created.
    """
    try:
        # FIXED: Replaced generic except with specific exception handling
        service = services.UnderwritingService(db)
        result = await service.evaluate_and_save(db, application_id, input_data, input_data.changed_by)
        
        return schemas.UnderwritingResultResponse(
            id=uuid.uuid4().int & 0x7FFFFFFF,  # Simplified ID generation
            application_id=application_id,
            created_at=result.created_at if hasattr(result, 'created_at') else None,
            **result.dict()
        )
    except ValueError as e:
        logger.warning("invalid_input_for_evaluation", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Invalid input data: {str(e)}", "error_code": "INVALID_INPUT"}
        )
    except Exception as e:
        # FIXED: Added context logging for exceptions
        logger.error("evaluation_failed", error=str(e), application_id=application_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": f"Evaluation failed: {str(e)}", "error_code": "EVALUATION_ERROR"}
        )


@router.get("/applications", response_model=schemas.UnderwritingApplicationList)
async def list_applications(
    *,
    db: AsyncSession = Depends(get_async_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    List underwriting applications with pagination.
    
    Returns a paginated list of underwriting applications with their results.
    """
    try:
        service = services.UnderwritingService(db)
        applications, total_count = await service.list_underwriting_applications(skip, limit)
        
        return schemas.UnderwritingApplicationList(
            applications=applications,
            total_count=total_count,
            skip=skip,
            limit=limit
        )
    except Exception as e:
        logger.error("listing_applications_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"detail": f"Failed to list applications: {str(e)}", "error_code": "LISTING_ERROR"}
        )
```

```