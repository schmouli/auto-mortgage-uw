⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `background_jobs` table** — Every table must include an `updated_at` column with `DateTime(timezone=True)` and `onupdate=func.now()` for audit purposes.  
🔧 Fix: Add `updated_at` to model with proper defaults and update behavior.

Issue 2: **No composite index on (`status`, `created_at`) for background job filtering** — Common query pattern in job workers filters by status and creation time; missing this index causes performance degradation.  
🔧 Fix: Add `Index('ix_background_jobs_status_created_at', 'status', 'created_at')` to the table definition.

Issue 3: **Foreign key `owner_id` missing `ondelete` parameter** — The `owner_id` FK to `users.id` does not define referential integrity action (`CASCADE`, `SET NULL`, etc.), risking orphaned records or constraint violations.  
🔧 Fix: Define `ForeignKey("users.id", ondelete="CASCADE")` explicitly.

Issue 4: **Service layer lacks pagination for job listing endpoint** — Endpoint `/jobs/` retrieves all jobs without limit/skip, leading to unbounded memory usage and poor performance.  
🔧 Fix: Update service method to accept `skip` and `limit` parameters (max 100), apply them in SQL query using `.offset().limit()`.

Issue 5: **N+1 detected in `job.result_log` access due to lazy-loading relationship** — Accessing `job.result_log` triggers individual SELECTs per job unless eagerly loaded. This breaks observability and latency SLAs.  
🔧 Fix: In relevant service functions, use `selectinload(Job.result_log)` when querying jobs to batch-load related data efficiently.

---

📚 LEARNINGS (compressed):  
1. [high] Always include `updated_at` with `onupdate=func.now()`  
2. [high] Composite indexes prevent seq scan on frequent filter combos  
3. [high] FKs must specify `ondelete` to enforce data lifecycle rules  
4. [high] Pagination is mandatory on all list endpoints  
5. [high] Eager load relationships via `selectinload()` to avoid N+1 queries