⚠️ BLOCKED  
Issue 1: **Float used for interest_rate and loan_amount** — violates financial precision requirement. Must use `Decimal` with appropriate scale.  
🔧 Fix: Change `FLOAT` → `Numeric(19, 4)` in column definitions.

Issue 2: **Missing updated_at field on decision_audit table** — breaks timestamp integrity rule.  
🔧 Fix: Add `updated_at = Column(DateTime(timezone=True), onupdate=func.now())`.

Issue 3: **No indexes on foreign keys (application_id, user_id)** — risks slow queries.  
🔧 Fix: Add `Index('ix_decision_application_id', 'application_id')`, same for `user_id`.

Issue 4: **Old-style relationship() without Mapped types detected** — not compliant with SQLAlchemy 2.0+.  
🔧 Fix: Replace `relationship("Application")` → `Mapped["Application"] = relationship(..., back_populates=...)`.

Issue 5: **decision_history endpoint does not implement pagination** — will cause performance issues at scale.  
🔧 Fix: Update service method to accept `skip`/`limit` and apply in SQL query (`LIMIT :limit OFFSET :skip`).

📚 LEARNINGS (compressed):  
1. [high] Use `Numeric(19,4)` for all financial fields – never `float`.  
2. [high] Always include `updated_at` with `onupdate=func.now()` on all tables.  
3. [high] Index all FKs – e.g., `Index('ix_table_fk_col', 'fk_col')`.  
4. [high] Prefer `Mapped[T] = relationship(..., back_populates=...)` for bidirectional sync.  
5. [high] Enforce max limit (e.g., 100) on paginated endpoints to prevent abuse.