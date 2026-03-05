⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `document_versions` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to model.

Issue 2: **Foreign key `document_id` in `document_versions` missing `ondelete` parameter**  
> Fix: Update ForeignKey to `ForeignKey("documents.id", ondelete="CASCADE")`

Issue 3: **No composite index found for common query pattern `(document_id, version_number)` in `document_versions`**  
> Fix: Add `__table_args__ = (Index('ix_document_version_docid_vernum', 'document_id', 'version_number'), )` to model

Issue 4: **Detected lazy-loading relationship between `Document` and `DocumentVersion` without explicit eager loading documented in service layer**  
> Fix: Ensure services use `selectinload(Document.versions)` or `joinedload(...)` to prevent N+1 queries

Issue 5: **List endpoint in service does not implement pagination (skip/limit)**  
> Fix: Modify method signature to accept `skip: int`, `limit: int` and apply `.offset().limit()` in query; enforce max limit of 100

📚 LEARNINGS (compressed):  
1. [high] Always define `updated_at` with `onupdate=func.now()` for audit trails  
2. [high] Specify `ondelete` policy for all ForeignKey definitions  
3. [med] Composite indexes improve performance for multi-column queries  
4. [high] Prevent N+1 via `selectinload()` or `joinedload()` in service queries  
5. [high] Enforce skip/limit pagination on all list operations  

Please address these issues before re-validation.