from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.mortgage.models import MortgageApplication
from mortgage_underwriting.modules.mortgage.schemas import ApplicationCreate, ApplicationResponse
from mortgage_underwriting.modules.mortgage.services import MyService

router = APIRouter(prefix="/api/v1/mortgage", tags=["Mortgage Applications"])

@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ApplicationCreate,
    db: AsyncSession = Depends(get_async_session),
) -> ApplicationResponse:
    """Create a new item. Raises 400 if validation fails."""
    service = MyService(db)
    try:
        result = await service.create(payload)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "VALIDATION_ERROR"})