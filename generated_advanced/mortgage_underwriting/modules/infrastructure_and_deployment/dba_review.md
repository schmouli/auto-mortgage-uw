⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `deployment_logs` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), onupdate=func.now())` to model.

Issue 2: **Email column missing index in `deployment_notifications` table**  
> Fix: Add `Index('ix_deployment_notifications_email', 'email')` to ensure performant lookups.

Issue 3: **Foreign key `deployment_id` in `deployment_logs` missing `ondelete` parameter**  
> Fix: Update ForeignKey to include `ondelete="CASCADE"` for safe cleanup of related logs.

Issue 4: **N+1 risk: `deployment` ↔ `deployment_logs` relationship not using eager loading in service queries**  
> Fix: Document and enforce use of `selectinload(Deployment.logs)` in relevant service methods.

Issue 5: **No pagination implemented in `list_deployments()` service method**  
> Fix: Add `skip: int = 0, limit: int = 100` parameters and apply `.offset().limit()` in query.

---

📚 LEARNINGS (compressed):  
1. [high] Always add `updated_at` to all tables with `onupdate=func.now()`  
2. [high] Index all email and FK columns for performance  
3. [high] Specify `ondelete` for all ForeignKey definitions  
4. [high] Prevent N+1 via documented eager loading (`selectinload`, `joinedload`)  
5. [high] Enforce skip/limit pagination on all list endpoints  

Please address these before re-validation.