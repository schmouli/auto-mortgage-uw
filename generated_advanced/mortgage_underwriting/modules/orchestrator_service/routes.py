from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from mortgage_underwriting.common.database import get_async_session
from mortgage_underwriting.modules.orchestrator.services import OrchestratorService
from mortgage_underwriting.modules.orchestrator.schemas import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse,
    TaskCreate, TaskUpdate, TaskResponse, TaskListResponse
)
from mortgage_underwriting.modules.orchestrator.exceptions import WorkflowNotFoundError, TaskNotFoundError

router = APIRouter(prefix="/api/v1/orchestrator", tags=["Orchestrator"])


@router.post("/workflows/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new orchestrator workflow."""
    service = OrchestratorService(db)
    return await service.create_workflow(payload)


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get an orchestrator workflow by ID."""
    service = OrchestratorService(db)
    workflow = await service.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Workflow not found", "error_code": "WORKFLOW_NOT_FOUND"}
        )
    return workflow


@router.patch("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: int,
    payload: WorkflowUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """Update an orchestrator workflow."""
    service = OrchestratorService(db)
    workflow = await service.update_workflow(workflow_id, payload)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Workflow not found", "error_code": "WORKFLOW_NOT_FOUND"}
        )
    return workflow


@router.get("/workflows/", response_model=list[WorkflowResponse])
async def list_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
):
    """List orchestrator workflows with pagination."""
    service = OrchestratorService(db)
    return await service.list_workflows(skip=skip, limit=limit)


@router.post("/tasks/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new orchestrator task."""
    service = OrchestratorService(db)
    return await service.create_task(payload)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get an orchestrator task by ID."""
    service = OrchestratorService(db)
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Task not found", "error_code": "TASK_NOT_FOUND"}
        )
    return task


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    """Update an orchestrator task."""
    service = OrchestratorService(db)
    task = await service.update_task(task_id, payload)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Task not found", "error_code": "TASK_NOT_FOUND"}
        )
    return task


@router.get("/tasks/", response_model=TaskListResponse)
async def list_tasks(
    workflow_id: Optional[int] = Query(None, description="Filter by workflow ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of items to return"),
    db: AsyncSession = Depends(get_async_session),
):
    """List orchestrator tasks with filtering and pagination."""
    service = OrchestratorService(db)
    return await service.list_tasks(workflow_id=workflow_id, status=status, skip=skip, limit=limit)
```

```