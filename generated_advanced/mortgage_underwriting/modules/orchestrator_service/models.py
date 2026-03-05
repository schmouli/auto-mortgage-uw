from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Boolean, Text, Index, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from decimal import Decimal
from mortgage_underwriting.common.database import Base


class OrchestratorWorkflow(Base):
    __tablename__ = "orchestrator_workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tasks: Mapped[list["OrchestratorTask"]] = relationship("OrchestratorTask", back_populates="workflow")


class OrchestratorTask(Base):
    __tablename__ = "orchestrator_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workflow_id: Mapped[int] = mapped_column(Integer, ForeignKey("orchestrator_workflows.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    estimated_completion_time: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    workflow: Mapped["OrchestratorWorkflow"] = relationship("OrchestratorWorkflow", back_populates="tasks")

# Composite index for workflow_id and status
Index('ix_orchestrator_task_workflow_status', 'workflow_id', 'status')
```

```