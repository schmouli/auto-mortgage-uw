⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `background_jobs` table** — Every model must include `updated_at` for audit purposes.  
🔧 Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to the model.

Issue 2: **No indexes defined on frequently queried columns (`status`, `scheduled_at`, `job_type`)** — Causes inefficient queries.  
🔧 Fix: Add individual and composite indexes:
```python
__table_args__ = (
    Index('ix_background_jobs_status', 'status'),
    Index('ix_background_jobs_scheduled_at', 'scheduled_at'),
    Index('ix_background_jobs_type_status', 'job_type', 'status'),
)
```

Issue 3: **Foreign key constraints missing `ondelete` policy** — Example: `owner_id` references `users.id` but lacks `ondelete="CASCADE"` or similar.  
🔧 Fix: Update ForeignKey definition:
```python
owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
```

Issue 4: **Lazy-loaded relationships may cause N+1 queries** — The `owner` relationship does not specify eager loading strategy.  
🔧 Fix: In services, ensure use of `selectinload(owner)` or `joinedload(owner)` when querying jobs with owner data.

Issue 5: **No pagination enforced in service layer** — List methods do not implement `skip`/`limit` pattern.  
🔧 Fix: Update service method signature to accept `skip: int = 0, limit: int = 100` and apply `.offset().limit()` in query.

Issue 6: **Job priority stored as Integer instead of Decimal** — Not a financial field per se, but if used in cost calculations, must use `Numeric`. Otherwise acceptable.

---

✅ APPROVED (after above fixes applied)  
Ensure all Alembic migrations follow safe practices: no DROP COLUMN, no RENAME, no NOT NULL without defaults.  

📚 LEARNINGS REINFORCED:  
1. Always include both `created_at` and `updated_at` on every model  
2. Index all FKs and commonly filtered/query-sorted fields  
3. Specify `ondelete` behavior for referential integrity  
4. Prevent N+1 via explicit eager loading (`selectinload`)  
5. Enforce pagination on all collection endpoints  
6. Never use `Float` for finance-related values — even indirect ones like weights, scores, or pseudo-currency fields should prefer `Decimal` where relevant