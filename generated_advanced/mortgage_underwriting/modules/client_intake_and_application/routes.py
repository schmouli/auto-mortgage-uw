--- routes.py ---
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.client_intake.services import ClientIntakeService, MortgageApplicationService
from mortgage_underwriting.modules.client_intake.schemas import (
    ClientCreate, ClientUpdate, ClientResponse,
    MortgageApplicationCreate, MortgageApplicationUpdate, MortgageApplicationResponse
)
from mortgage_underwriting.modules.client_intake.exceptions import ClientIntakeException

router = APIRouter(prefix="/api/v1/client-intake", tags=["Client Intake"])


def get_client_service(db: AsyncSession = Depends(get_async_session)) -> ClientIntakeService:
    return ClientIntakeService(db)


def get_application_service(db: AsyncSession = Depends(get_async_session)) -> MortgageApplicationService:
    return MortgageApplicationService(db)


@router.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    client_data: ClientCreate,
    service: ClientIntakeService = Depends(get_client_service)
):
    """Create a new client with associated addresses.
    
    Args:
        client_data: Client creation data including addresses
        
    Returns:
        Created client object
        
    Raises:
        HTTPException: If client creation fails
    """
    try:
        return await service.create_client(client_data)
    except ClientIntakeException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": e.message, "error_code": e.code})


@router.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    service: ClientIntakeService = Depends(get_client_service)
):
    """Get a client by ID with associated addresses and applications.
    
    Args:
        client_id: ID of the client to fetch
        
    Returns:
        Client object
        
    Raises:
        HTTPException: If client not found
    """
    client = await service.get_client_by_id(client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": "Client not found", "error_code": "CLIENT_NOT_FOUND"})
    return client


@router.put("/clients/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    client_data: ClientUpdate,
    service: ClientIntakeService = Depends(get_client_service)
):
    """Update a client's information.
    
    Args:
        client_id: ID of the client to update
        client_data: Updated client data
        
    Returns:
        Updated client object
        
    Raises:
        HTTPException: If client not found or update fails
    """
    try:
        client = await service.update_client(client_id, client_data)
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": "Client not found", "error_code": "CLIENT_NOT_FOUND"})
        return client
    except ClientIntakeException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": e.message, "error_code": e.code})


@router.post("/applications", response_model=MortgageApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    application_data: MortgageApplicationCreate,
    service: MortgageApplicationService = Depends(get_application_service)
):
    """Create a new mortgage application.
    
    Args:
        application_data: Application creation data
        
    Returns:
        Created application object
        
    Raises:
        HTTPException: If application creation fails
    """
    try:
        return await service.create_application(application_data)
    except ClientIntakeException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": e.message, "error_code": e.code})


@router.get("/applications/{application_id}", response_model=MortgageApplicationResponse)
async def get_application(
    application_id: int,
    service: MortgageApplicationService = Depends(get_application_service)
):
    """Get a mortgage application by ID.
    
    Args:
        application_id: ID of the application to fetch
        
    Returns:
        Application object
        
    Raises:
        HTTPException: If application not found
    """
    application = await service.get_application_by_id(application_id)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": "Application not found", "error_code": "APPLICATION_NOT_FOUND"})
    return application


@router.put("/applications/{application_id}", response_model=MortgageApplicationResponse)
async def update_application(
    application_id: int,
    application_data: MortgageApplicationUpdate,
    service: MortgageApplicationService = Depends(get_application_service)
):
    """Update a mortgage application.
    
    Args:
        application_id: ID of the application to update
        application_data: Updated application data
        
    Returns:
        Updated application object
        
    Raises:
        HTTPException: If application not found or update fails
    """
    try:
        application = await service.update_application(application_id, application_data)
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"detail": "Application not found", "error_code": "APPLICATION_NOT_FOUND"})
        return application
    except ClientIntakeException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": e.message, "error_code": e.code})


@router.get("/applications/{application_id}/gds-tds")
async def calculate_gds_tds(
    application_id: int,
    service: MortgageApplicationService = Depends(get_application_service)
):
    """Calculate GDS and TDS ratios for an application per OSFI B-20 guidelines.
    
    Args:
        application_id: ID of the application to analyze
        
    Returns:
        Dictionary containing GDS/TDS calculations and compliance status
        
    Raises:
        HTTPException: If application not found or calculation fails
    """
    try:
        return await service.calculate_gds_tds(application_id)
    except ClientIntakeException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": e.message, "error_code": e.code})