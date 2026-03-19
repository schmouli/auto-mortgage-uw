from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.client_portal.schemas import (
    LoginRequest, TokenResponse, RefreshTokenRequest,
    ClientDashboardResponse, BrokerDashboardResponse,
    ApplicationSummaryResponse, ApplicationDetailResponse,
    DocumentChecklistItem, NotificationResponse,
    DocumentUploadRequest, NotificationReadRequest, NotificationReadAllRequest
)
from mortgage_underwriting.modules.client_portal.services import ClientPortalService

router = APIRouter(prefix="/api/v1/client-portal", tags=["Client Portal"])

# Dependency


async def get_client_portal_service(db: AsyncSession = Depends(get_async_session)) -> ClientPortalService:
    return ClientPortalService(db)

# Authentication Routes

@router.post("/auth/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    service: ClientPortalService = Depends(get_client_portal_service)
):
    try:
        return await service.authenticate_client(payload)
    except NotImplementedError:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail={"detail": "Not Implemented", "error_code": "NOT_IMPLEMENTED"})

@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout():
    # Logout handled client-side by deleting tokens
    return

@router.post("/auth/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh_token(
    payload: RefreshTokenRequest,
    service: ClientPortalService = Depends(get_client_portal_service)
):
    try:
        return await service.refresh_client_token(payload)
    except NotImplementedError:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail={"detail": "Not Implemented", "error_code": "NOT_IMPLEMENTED"})

# Dashboard Routes

@router.get("/dashboard/client", response_model=ClientDashboardResponse)
async def get_client_dashboard(
    client_id: int, # In real implementation, extract from auth token
    service: ClientPortalService = Depends(get_client_portal_service)
):
    try:
        return await service.get_client_dashboard(client_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": str(e), "error_code": "INTERNAL_ERROR"})

@router.get("/dashboard/broker", response_model=BrokerDashboardResponse)
async def get_broker_dashboard(
    broker_id: int, # In real implementation, extract from auth token
    service: ClientPortalService = Depends(get_client_portal_service)
):
    try:
        return await service.get_broker_dashboard(broker_id)
    except NotImplementedError:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail={"detail": "Not Implemented", "error_code": "NOT_IMPLEMENTED"})

# Application Routes

@router.get("/applications", response_model=List[ApplicationSummaryResponse])
async def list_applications(
    client_id: int, # Extract from auth token
    service: ClientPortalService = Depends(get_client_portal_service)
):
    try:
        return await service.list_client_applications(client_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": str(e), "error_code": "INTERNAL_ERROR"})

@router.get("/applications/{application_id}", response_model=ApplicationDetailResponse)
async def get_application(
    application_id: int,
    client_id: int, # Extract from auth token
    service: ClientPortalService = Depends(get_client_portal_service)
):
    try:
        return await service.get_application_detail(application_id, client_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": str(e), "error_code": "INTERNAL_ERROR"})

# Document Routes

@router.get("/applications/{application_id}/checklist", response_model=List[DocumentChecklistItem])
async def get_document_checklist(
    application_id: int,
    client_id: int, # Extract from auth token
    service: ClientPortalService = Depends(get_client_portal_service)
):
    try:
        return await service.get_document_checklist(application_id, client_id)
    except NotImplementedError:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail={"detail": "Not Implemented", "error_code": "NOT_IMPLEMENTED"})

@router.post("/applications/{application_id}/documents/upload")
async def upload_document(
    application_id: int,
    client_id: int, # Extract from auth token
    payload: DocumentUploadRequest,
    background_tasks: BackgroundTasks,
    service: ClientPortalService = Depends(get_client_portal_service)
):
    try:
        # In real implementation, handle file upload and save to storage
        return await service.upload_document(client_id, application_id, payload.dict())
    except NotImplementedError:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail={"detail": "Not Implemented", "error_code": "NOT_IMPLEMENTED"})

# Notification Routes

@router.get("/notifications", response_model=List[NotificationResponse])
async def list_notifications(
    client_id: int, # Extract from auth token
    service: ClientPortalService = Depends(get_client_portal_service)
):
    try:
        return await service.list_notifications(client_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": str(e), "error_code": "INTERNAL_ERROR"})

@router.put("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    notification_id: int,
    client_id: int, # Extract from auth token
    service: ClientPortalService = Depends(get_client_portal_service)
):
    try:
        await service.mark_notification_as_read(notification_id, client_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": str(e), "error_code": "INTERNAL_ERROR"})

@router.put("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_notifications_read(
    client_id: int, # Extract from auth token
    service: ClientPortalService = Depends(get_client_portal_service)
):
    try:
        await service.mark_all_notifications_as_read(client_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"detail": str(e), "error_code": "INTERNAL_ERROR"})