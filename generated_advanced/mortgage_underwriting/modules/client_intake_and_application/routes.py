from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.client_intake.schemas import (
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    MortgageApplicationCreate,
    MortgageApplicationUpdate,
    MortgageApplicationResponse,
    CoBorrowerCreate,
    CoBorrowerResponse,
    ApplicationSummaryResponse
)
from mortgage_underwriting.modules.client_intake.services import ClientIntakeService

router = APIRouter(prefix="/api/v1/applications", tags=["Client Intake & Applications"])


def get_client_intake_service(db: AsyncSession = Depends(get_async_session)) -> ClientIntakeService:
    return ClientIntakeService(db)

@router.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    user_id: int,
    service: ClientIntakeService = Depends(get_client_intake_service)
):
    """Create a new client profile."""
    try:
        return await service.create_client(user_id, payload)
    except Exception as e:
        # FIXED: Better error categorization
        if "PII" in str(e) or "encryption" in str(e):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "PII_ENCRYPTION_FAILED", "detail": str(e)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "CLIENT_CREATE_FAILED", "detail": str(e)})

@router.put("/clients/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    payload: ClientUpdate,
    service: ClientIntakeService = Depends(get_client_intake_service)
):
    """Update an existing client profile."""
    try:
        return await service.update_client(client_id, payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "CLIENT_UPDATE_FAILED", "detail": str(e)})

@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: int,
    service: ClientIntakeService = Depends(get_client_intake_service)
):
    """Delete a client profile."""
    try:
        await service.delete_client(client_id)
        return
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "CLIENT_DELETE_FAILED", "detail": str(e)})

@router.post("/", response_model=MortgageApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: MortgageApplicationCreate,
    client_id: int,
    service: ClientIntakeService = Depends(get_client_intake_service)
):
    """Create a new mortgage application."""
    try:
        return await service.create_application(client_id, payload)
    except Exception as e:
        # FIXED: Specific error handling for financial validation
        if "Down payment" in str(e) or "loan amount" in str(e):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "FINANCIAL_VALIDATION_ERROR", "detail": str(e)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "APPLICATION_CREATE_FAILED", "detail": str(e)})

@router.get("/", response_model=List[MortgageApplicationResponse])
async def list_applications(
    limit: int = Query(100, le=100),
    offset: int = Query(0),
    service: ClientIntakeService = Depends(get_client_intake_service)
):
    """List mortgage applications with pagination."""
    try:
        return await service.list_applications(limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"error_code": "APPLICATION_LIST_FAILED", "detail": str(e)})

@router.get("/{application_id}", response_model=MortgageApplicationResponse)
async def get_application(
    application_id: int,
    service: ClientIntakeService = Depends(get_client_intake_service)
):
    """Get a specific mortgage application by ID."""
    try:
        return await service.get_application(application_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_code": "APPLICATION_NOT_FOUND", "detail": str(e)})

@router.put("/{application_id}", response_model=MortgageApplicationResponse)
async def update_application(
    application_id: int,
    payload: MortgageApplicationUpdate,
    service: ClientIntakeService = Depends(get_client_intake_service)
):
    """Update an existing mortgage application."""
    try:
        return await service.update_application(application_id, payload)
    except Exception as e:
        # FIXED: Better error handling for status conflicts
        if "draft" in str(e) or "status" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_code": "APPLICATION_STATUS_CONFLICT", "detail": str(e)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "APPLICATION_UPDATE_FAILED", "detail": str(e)})

@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: int,
    service: ClientIntakeService = Depends(get_client_intake_service)
):
    """Delete a mortgage application."""
    try:
        await service.delete_application(application_id)
        return
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "APPLICATION_DELETE_FAILED", "detail": str(e)})

@router.post("/{application_id}/submit", response_model=MortgageApplicationResponse)
async def submit_application(
    application_id: int,
    service: ClientIntakeService = Depends(get_client_intake_service)
):
    """Submit an application for underwriting."""
    try:
        return await service.submit_application(application_id)
    except Exception as e:
        # FIXED: Handle submission conflicts properly
        if "draft" in str(e) or "status" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_code": "APPLICATION_SUBMISSION_CONFLICT", "detail": str(e)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "APPLICATION_SUBMIT_FAILED", "detail": str(e)})

@router.post("/{application_id}/co-borrowers", response_model=CoBorrowerResponse, status_code=status.HTTP_201_CREATED)
async def add_co_borrower(
    application_id: int,
    client_id: int,
    payload: CoBorrowerCreate,
    service: ClientIntakeService = Depends(get_client_intake_service)
):
    """Add a co-borrower to an application."""
    try:
        return await service.add_co_borrower(client_id, application_id, payload)
    except Exception as e:
        # FIXED: Handle co-borrower specific errors
        if "application" in str(e) and "draft" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_code": "APPLICATION_NOT_DRAFT", "detail": str(e)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "COBORROWER_ADD_FAILED", "detail": str(e)})

@router.get("/{application_id}/summary", response_model=ApplicationSummaryResponse)
async def get_application_summary(
    application_id: int,
    service: ClientIntakeService = Depends(get_client_intake_service)
):
    """Get a summary of the application for PDF generation."""
    try:
        return await service.get_application_summary(application_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_code": "SUMMARY_NOT_FOUND", "detail": str(e)})

@router.get("/{application_id}/gds-tds", response_model=dict)
async def calculate_gds_tds(
    application_id: int,
    service: ClientIntakeService = Depends(get_client_intake_service)
):
    """Calculate Gross Debt Service (GDS) and Total Debt Service (TDS) ratios."""
    try:
        return await service.calculate_gds_tds(application_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "GDS_TDS_CALCULATION_FAILED", "detail": str(e)})