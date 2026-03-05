"""Client portal routes for mortgage underwriting system."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.client_portal.services import ClientPortalService
from mortgage_underwriting.modules.client_portal.schemas import (
    ClientCreate, 
    ClientUpdate, 
    ClientResponse,
    SessionCreate,
    SessionResponse
)

router = APIRouter(prefix="/api/v1/client-portal", tags=["Client Portal"])


@router.post("/clients/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new client. Raises 400 if validation fails."""
    service = ClientPortalService(db)
    try:
        return await service.create_client(payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "CLIENT_CREATION_FAILED", "detail": str(e)}
        )


@router.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific client by ID."""
    service = ClientPortalService(db)
    client = await service.get_client(client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "CLIENT_NOT_FOUND", "detail": f"Client with ID {client_id} not found"}
        )
    return client


@router.get("/clients/", response_model=List[ClientResponse])
async def get_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a list of clients with pagination."""
    service = ClientPortalService(db)
    return await service.get_clients(skip, limit)


@router.put("/clients/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """Update an existing client."""
    service = ClientPortalService(db)
    client = await service.update_client(client_id, payload)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "CLIENT_NOT_FOUND", "detail": f"Client with ID {client_id} not found"}
        )
    return client


@router.post("/sessions/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new client portal session."""
    service = ClientPortalService(db)
    return await service.create_session(payload)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific session by ID."""
    service = ClientPortalService(db)
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "SESSION_NOT_FOUND", "detail": f"Session with ID {session_id} not found"}
        )
    return session


@router.get("/sessions/", response_model=List[SessionResponse])
async def get_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a list of sessions with pagination."""
    service = ClientPortalService(db)
    return await service.get_sessions(skip, limit)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def invalidate_session(
    session_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """Invalidate a client portal session."""
    service = ClientPortalService(db)
    success = await service.invalidate_session(session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "SESSION_NOT_FOUND", "detail": f"Session with ID {session_id} not found"}
        )
```

```