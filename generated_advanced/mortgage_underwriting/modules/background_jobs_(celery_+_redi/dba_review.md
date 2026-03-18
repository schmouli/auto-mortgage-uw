⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `jobs` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to model.

Issue 2: **Foreign key `client_id` missing `ondelete` parameter**  
> Fix: Update ForeignKey definition to include `ondelete="CASCADE"` or appropriate constraint.

Issue 3: **No composite index on (`status`, `scheduled_at`) — common query pattern for job filtering**  
> Fix: Add `Index('ix_jobs_status_scheduled_at', 'status', 'scheduled_at')` for performance.

Issue 4: **Lazy-loaded relationship detected on `Job.client` without explicit eager loading strategy in services**  
> Fix: Annotate with `selectinload(Job.client)` or `joinedload(Job.client)` in service queries to prevent N+1.

Issue 5: **No pagination implemented in `get_jobs()` service method**  
> Fix: Add `skip: int`, `limit: int` parameters (max 100), and apply `.offset().limit()` in query.

---

📚 LEARNINGS (compressed):  
1. [high] Always add `updated_at` with `onupdate=func.now()` for auditability  
2. [high] Specify `ondelete` for all foreign keys to ensure referential integrity  
3. [high] Composite indexes prevent full-table scans on multi-field filters  
4. [high] Eager load relationships explicitly to avoid N+1 in async services  
5. [high] Paginate all list endpoints to prevent memory exhaustion  

🔁 NEXT STEP: Re-generate models with fixes applied and resubmit for review.