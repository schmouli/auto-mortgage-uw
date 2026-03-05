⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `document_audit_log` table**  
- Fix: Add `updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())`  

Issue 2: **Float used for `confidence_score` in `ProcessedDocument` model**  
- Fix: Change to `Numeric(5, 4)` or equivalent Decimal type for precision  

Issue 3: **Missing composite index on (`status`, `client_id`) in `DocumentProcessingJob`**  
- Fix: Add `Index('ix_doc_processing_status_client', 'status', 'client_id')`  

Issue 4: **Foreign key `document_id` in `document_audit_log` missing `ondelete` parameter**  
- Fix: Update ForeignKey to include `ondelete="CASCADE"` or appropriate referential action  

Issue 5: **N+1 query risk in `get_document_with_related_jobs()` service method**  
- Fix: Eager load related jobs using `selectinload(DocumentProcessingJob.related_jobs)`  

Issue 6: **List endpoint in `services.py` does not implement pagination (skip/limit)**  
- Fix: Add `skip: int = 0, limit: int = 100` parameters and apply in query  

📚 LEARNINGS (compressed):  
1. [high] Always pair `created_at` with `updated_at` including `onupdate=func.now()`  
2. [high] Never use Float for scores or any numeric data needing precision – prefer Decimal  
3. [high] Composite indexes prevent full-table scans on filtered queries like status + client_id  
4. [high] Foreign keys must define `ondelete` to ensure integrity during deletes  
5. [high] Prevent N+1 by declaring eager loading strategies explicitly in service layers  
6. [high] Paginate all list endpoints with configurable skip/limit (max 100 per page)