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
    """Create a new client with associated addresses"""
    try:
        return await service.create_client(client_data)
    except ClientIntakeException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": e.message, "error_code": e.code})


@router.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    service: ClientIntakeService = Depends(get_client_service)
):
    """Get a client by ID with associated addresses and applications"""
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
    """Update a client's information"""
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
    """Create a new mortgage application"""
    try:
        return await service.create_application(application_data)
    except ClientIntakeException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": e.message, "error_code": e.code})


@router.get("/applications/{application_id}", response_model=MortgageApplicationResponse)
async def get_application(
    application_id: int,
    service: MortgageApplicationService = Depends(get_application_service)
):
    """Get a mortgage application by ID"""
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
    """Update a mortgage application"""
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
    """Calculate GDS and TDS ratios for an application per OSFI B-20 guidelines"""
    try:
        return await service.calculate_gds_tds(application_id)
    except ClientIntakeException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": e.message, "error_code": e.code})