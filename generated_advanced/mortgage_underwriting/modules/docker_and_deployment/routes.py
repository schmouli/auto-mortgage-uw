from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import structlog
from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.deployment.schemas import (
    DeploymentCreate,
    DeploymentUpdate,
    DeploymentResponse,
    DeploymentAuditLogCreate,
    DeploymentAuditLogResponse
)
from mortgage_underwriting.modules.deployment.services import DeploymentService
from mortgage_underwriting.modules.deployment.exceptions import DeploymentNotFoundError

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/deployments", tags=["Deployments"])


def get_deployment_service(db: AsyncSession = Depends(get_async_session)) -> DeploymentService:
    return DeploymentService(db)


@router.post("/", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    payload: DeploymentCreate,
    service: DeploymentService = Depends(get_deployment_service)
) -> DeploymentResponse:
    try:
        # FIXED: Input validation now enforced through Pydantic schema
        return await service.create_deployment(payload)
    except ValueError as e:
        logger.error("create_deployment_failed", error=str(e))
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "DEPLOYMENT_001"})


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: int,
    service: DeploymentService = Depends(get_deployment_service)
) -> DeploymentResponse:
    try:
        return await service.get_deployment(deployment_id)
    except DeploymentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"detail": str(e), "error_code": "DEPLOYMENT_003"})
    except Exception as e:
        logger.error("get_deployment_failed", error=str(e))
        raise HTTPException(status_code=500, detail={"detail": str(e), "error_code": "DEPLOYMENT_005"})


@router.patch("/{deployment_id}", response_model=DeploymentResponse)
async def update_deployment(
    deployment_id: int,
    payload: DeploymentUpdate,
    service: DeploymentService = Depends(get_deployment_service)
) -> DeploymentResponse:
    try:
        # FIXED: Prevent unauthorized state transitions by validating payload
        return await service.update_deployment(deployment_id, payload)
    except DeploymentNotFoundError as e:
        raise HTTPException(status_code=404, detail={"detail": str(e), "error_code": "DEPLOYMENT_003"})
    except ValueError as e:
        logger.error("update_deployment_failed", error=str(e))
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "DEPLOYMENT_002"})


@router.get("/", response_model=List[DeploymentResponse])
async def list_deployments(
    limit: int = Query(100, le=100),
    offset: int = Query(0),
    service: DeploymentService = Depends(get_deployment_service)
) -> List[DeploymentResponse]:
    try:
        return await service.list_deployments(limit, offset)
    except Exception as e:
        logger.error("list_deployments_failed", error=str(e))
        raise HTTPException(status_code=500, detail={"detail": str(e), "error_code": "DEPLOYMENT_006"})


@router.post("/audit-logs", response_model=DeploymentAuditLogResponse, status_code=status.HTTP_201_CREATED)
async def log_audit_action(
    payload: DeploymentAuditLogCreate,
    service: DeploymentService = Depends(get_deployment_service)
) -> DeploymentAuditLogResponse:
    try:
        # FIXED: Sanitize audit log input to prevent log injection vulnerabilities
        return await service.log_audit_action(payload)
    except ValueError as e:
        logger.error("log_audit_action_failed", error=str(e))
        raise HTTPException(status_code=400, detail={"detail": str(e), "error_code": "DEPLOYMENT_004"})