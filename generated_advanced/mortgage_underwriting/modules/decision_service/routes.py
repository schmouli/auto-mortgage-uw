from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.clients.schemas import ClientCreate, ClientUpdate, ClientResponse
from mortgage_underwriting.modules.clients.services import ClientService
from mortgage_underwriting.modules.clients.exceptions import ClientNotFoundError, ClientAlreadyExistsError

router = APIRouter(prefix="/api/v1/clients", tags=["Clients"])


def get_client_service(db: AsyncSession = Depends(get_async_session)) -> ClientService:
    return ClientService(db)


@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    service: ClientService = Depends(get_client_service),
) -> ClientResponse:
    try:
        return await service.create_client(payload)
    except ClientAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": f"Client with email {e.email} already exists", "error_code": "CLIENT_EXISTS"}
        )


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    service: ClientService = Depends(get_client_service),
) -> ClientResponse:
    try:
        return await service.get_client(client_id)
    except ClientNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": f"Client with ID {e.client_id} not found", "error_code": "CLIENT_NOT_FOUND"}
        )


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    payload: ClientUpdate,
    service: ClientService = Depends(get_client_service),
) -> ClientResponse:
    try:
        return await service.update_client(client_id, payload)
    except ClientNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": f"Client with ID {e.client_id} not found", "error_code": "CLIENT_NOT_FOUND"}
        )


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: int,
    service: ClientService = Depends(get_client_service),
) -> None:
    try:
        await service.delete_client(client_id)
    except ClientNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": f"Client with ID {e.client_id} not found", "error_code": "CLIENT_NOT_FOUND"}
        )