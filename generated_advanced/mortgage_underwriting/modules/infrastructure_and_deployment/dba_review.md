⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `deployment_events` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), onupdate=func.now())` to model.

Issue 2: **Email column missing index in `infrastructure_providers` table**  
> Fix: Add `__table_args__ = (Index('ix_infrastructure_providers_email', 'email'),)` to model.

Issue 3: **Foreign key `provider_id` missing `ondelete` parameter in `deployment_events`**  
> Fix: Update ForeignKey to `ForeignKey("infrastructure_providers.id", ondelete="CASCADE")`

Issue 4: **Detected lazy-loading relationship in `DeploymentEvent` referencing `InfrastructureProvider`**  
> Fix: Annotate relationship with `Mapped["InfrastructureProvider"]` and add `selectinload()` in service query

Issue 5: **No pagination enforced in `list_deployments()` service method**  
> Fix: Add `skip: int = 0, limit: int = 100` params and apply `.offset().limit()` in query

📚 LEARNINGS (compressed):  
1. [high] Always include updated_at with onupdate=func.now()  
2. [high] Index all FKs and frequent lookup fields like email  
3. [high] Specify ondelete behavior for referential integrity  
4. [high] Prevent N+1 via selectinload/joinedload in services  
5. [high] Enforce skip/limit in all list endpoints  

✅ AFTER FIXES — RE-RUN VALIDATION TO CONFIRM APPROVAL