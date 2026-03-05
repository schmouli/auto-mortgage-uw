import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional, List

from mortgage_underwriting.modules.orchestrator.models import OrchestratorWorkflow, OrchestratorTask
from mortgage_underwriting.modules.orchestrator.schemas import WorkflowCreate, WorkflowUpdate, TaskCreate, TaskUpdate, TaskListResponse

logger = structlog.get_logger()


class OrchestratorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_workflow(self, payload: WorkflowCreate) -> OrchestratorWorkflow:
        logger.info("creating_workflow")
        workflow = OrchestratorWorkflow(**payload.model_dump())
        self.db.add(workflow)
        await self.db.commit()
        await self.db.refresh(workflow)
        return workflow

    async def get_workflow(self, workflow_id: int) -> Optional[OrchestratorWorkflow]:
        logger.info("fetching_workflow", workflow_id=workflow_id)
        stmt = select(OrchestratorWorkflow).where(OrchestratorWorkflow.id == workflow_id).options(selectinload(OrchestratorWorkflow.tasks))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_workflow(self, workflow_id: int, payload: WorkflowUpdate) -> Optional[OrchestratorWorkflow]:
        logger.info("updating_workflow", workflow_id=workflow_id)
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            return None
        
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(workflow, key, value)
            
        await self.db.commit()
        await self.db.refresh(workflow)
        return workflow

    async def create_task(self, payload: TaskCreate) -> OrchestratorTask:
        logger.info("creating_task")
        task = OrchestratorTask(**payload.model_dump())
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_task(self, task_id: int) -> Optional[OrchestratorTask]:
        logger.info("fetching_task", task_id=task_id)
        stmt = select(OrchestratorTask).where(OrchestratorTask.id == task_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_task(self, task_id: int, payload: TaskUpdate) -> Optional[OrchestratorTask]:
        logger.info("updating_task", task_id=task_id)
        task = await self.get_task(task_id)
        if not task:
            return None
        
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(task, key, value)
            
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def list_tasks(self, workflow_id: Optional[int] = None, status: Optional[str] = None, 
                        skip: int = 0, limit: int = 100) -> TaskListResponse:
        logger.info("listing_tasks", workflow_id=workflow_id, status=status, skip=skip, limit=limit)
        
        # Ensure limit doesn't exceed maximum
        limit = min(limit, 100)
        
        # Base query
        stmt = select(OrchestratorTask)
        
        # Apply filters
        if workflow_id is not None:
            stmt = stmt.where(OrchestratorTask.workflow_id == workflow_id)
        if status is not None:
            stmt = stmt.where(OrchestratorTask.status == status)
            
        # Apply pagination
        stmt = stmt.offset(skip).limit(limit)
        
        # Execute query for items
        result = await self.db.execute(stmt)
        items = result.scalars().all()
        
        # Count total matching records
        count_stmt = select(func.count()).select_from(OrchestratorTask)
        if workflow_id is not None:
            count_stmt = count_stmt.where(OrchestratorTask.workflow_id == workflow_id)
        if status is not None:
            count_stmt = count_stmt.where(OrchestratorTask.status == status)
            
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar_one()
        
        return TaskListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit
        )

    async def list_workflows(self, skip: int = 0, limit: int = 100) -> List[OrchestratorWorkflow]:
        logger.info("listing_workflows", skip=skip, limit=limit)
        
        # Ensure limit doesn't exceed maximum
        limit = min(limit, 100)
        
        stmt = select(OrchestratorWorkflow).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()
```

```