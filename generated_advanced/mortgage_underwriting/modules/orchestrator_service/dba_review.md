⚠️ BLOCKED  
Issue 1: **Missing `updated_at` field with `onupdate=func.now()`** on table `orchestrator_workflow`  
🔧 Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())`  

Issue 2: **Float used for `estimated_completion_time` column** in `orchestrator_task` table  
🔧 Fix: Replace `Float` with `Numeric(19, 4)` for financial/time precision compliance  

Issue 3: **Missing composite index** on (`workflow_id`, `status`) in `orchestrator_task`  
🔧 Fix: Add `Index('ix_orchestrator_task_workflow_status', 'workflow_id', 'status')` for query performance  

Issue 4: **N+1 query risk detected** — relationship `tasks` in `OrchestratorWorkflow` uses lazy loading  
🔧 Fix: In service layer, load with `selectinload(workflow.tasks)` to prevent N+1  

Issue 5: **No pagination enforced in task listing service method**  
🔧 Fix: Add `skip: int = 0, limit: int = 100` parameters and apply `.offset().limit()` in query  

📚 LEARNINGS (compressed):  
1. Always pair `created_at` with `updated_at` using `server_default` and `onupdate`  
2. Never use `Float` for any numeric value requiring precision – use `Decimal`  
3. Composite indexes must match common query filters to avoid full table scans  
4. Eager load relationships explicitly via `selectinload()` or `joinedload()`  
5. All list endpoints must enforce pagination with `skip`/`limit` (max 100)