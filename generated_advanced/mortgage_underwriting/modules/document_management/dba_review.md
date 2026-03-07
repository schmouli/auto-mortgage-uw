⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `document_versions` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())` to model.

Issue 2: **Foreign key `document_id` in `document_versions` lacks `ondelete` parameter**  
> Fix: Update ForeignKey to: `ForeignKey("documents.id", ondelete="CASCADE")`

Issue 3: **No composite index on `documents.client_id` + `documents.created_at` for common query patterns**  
> Fix: Add `Index('ix_documents_client_created', 'client_id', 'created_at')` to optimize client document listings.

Issue 4: **Service method `list_documents()` does not implement pagination (skip/limit)**  
> Fix: Accept `skip: int`, `limit: int` params; apply `.offset(skip).limit(min(limit, 100))` in query.

Issue 5: **Email lookup column `uploaded_by_email` exists but has no index**  
> Fix: Add index with `Index('ix_documents_uploaded_by_email', 'uploaded_by_email')`  

---

📚 LEARNINGS (compressed):  
1. [high] Always add `updated_at` with `onupdate=func.now()`  
2. [high] FKs need `ondelete` to prevent orphaned data  
3. [med] Composite indexes speed up multi-field queries  
4. [high] Paginate all list endpoints (`skip`/`limit`)  
5. [low] Index email columns used for filtering