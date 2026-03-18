⚠️ BLOCKED  
Issue 1: **Missing `updated_at` field on `report_configurations` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())`  

Issue 2: **Foreign key `user_id` in `report_runs` missing `ondelete` parameter**  
> Fix: Update to `ForeignKey("users.id", ondelete="CASCADE")`  

Issue 3: **No composite index on `report_runs.user_id + report_runs.created_at`**  
> Fix: Add `Index('ix_report_runs_user_created', 'user_id', 'created_at')` for performance  

Issue 4: **Float used for `execution_time_ms` (financial proxy metric)**  
> Fix: Change column type to `Numeric(10, 4)`  

Issue 5: **List service method `get_report_runs()` does not implement pagination (skip/limit)**  
> Fix: Add `skip: int = 0, limit: int = 100` parameters and apply in query  

📚 LEARNINGS (compressed):  
1. [high] Always include `updated_at` with `onupdate=func.now()`  
2. [high] Specify `ondelete` behavior for all foreign keys  
3. [high] Composite indexes prevent full-table scans on multi-key filters  
4. [high] Never use float for metrics that may be financial or precise  
5. [high] Paginate all list endpoints with `offset`/`limit` in DB query