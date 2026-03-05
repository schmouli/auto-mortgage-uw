from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from mortgage_underwriting.common.database import get_async_session
from .services import ReportingService
from .schemas import ReportCreate, ReportUpdate, ReportResponse
from typing import List

router = APIRouter(prefix="/api/v1/reports", tags=["Reporting & Analytics"])


@router.get("/", response_model=List[ReportResponse])
async def list_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100, ge=1),
    db: AsyncSession = Depends(get_async_session),
):
    """Retrieve a paginated list of reports."""
    service = ReportingService(db)
    return await service.get_reports_list(skip=skip, limit=limit)


@router.post("/", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: ReportCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new report."""
    service = ReportingService(db)
    try:
        return await service.create_report(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": str(e), "error_code": "REPORT_CREATION_FAILED"}
        )


@router.patch("/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: int,
    payload: ReportUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """Update an existing report."""
    service = ReportingService(db)
    try:
        return await service.update_report(report_id, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": str(e), "error_code": "REPORT_NOT_FOUND"}
        )
```

```