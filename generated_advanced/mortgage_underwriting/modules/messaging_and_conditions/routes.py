from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.mortgage.models import MortgageApplication
from mortgage_underwriting.modules.mortgage.schemas import ApplicationCreate, ApplicationResponse
from mortgage_underwriting.modules.mortgage.services import MyService
from mortgage_underwriting.modules.mortgage.exceptions import MortgageApplicationError
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/mortgage", tags=["Mortgage Applications"])

@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ApplicationCreate,
    db: AsyncSession = Depends(get_async_session),
) -> ApplicationResponse:
    """Create a new mortgage application. Raises 400 if validation fails."""
    service = MyService(db)
    try:
        result = await service.create(payload)
        return result
    except MortgageApplicationError as e:
        logger.warning("mortgage_application_creation_rejected", error=str(e))
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "APPLICATION_CREATE_FAILED"})
    except Exception as e:
        logger.error("route_unhandled_exception", error=str(e))
        raise HTTPException(status_code=500, detail={"detail": "Internal server error", "error_code": "UNHANDLED_ERROR"})