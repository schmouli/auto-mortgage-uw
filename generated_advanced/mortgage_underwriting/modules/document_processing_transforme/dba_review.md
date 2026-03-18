⚠️ BLOCKED  
Issue 1: **Missing `updated_at` field on `document_packages` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())`  

Issue 2: **Foreign key `client_id` in `document_packages` missing `ondelete` parameter**  
> Fix: Update to `ForeignKey("clients.id", ondelete="CASCADE")`  

Issue 3: **No index on `email` column in `clients` table**  
> Fix: Add `Index('ix_clients_email', 'email')`  

Issue 4: **Float used for `confidence_score` in `processed_documents`**  
> Fix: Replace with `Numeric(5, 4)` for precision  

Issue 5: **Missing composite index for `(status, client_id)` in `document_packages`**  
> Fix: Add `Index('ix_document_packages_status_client', 'status', 'client_id')`  

Issue 6: **Lazy-loaded relationship `documents` in `DocumentPackage` may cause N+1**  
> Fix: Annotate service queries with `selectinload(DocumentPackage.documents)`  

Issue 7: **List retrieval in `services.py` lacks pagination (`skip`, `limit`)**  
> Fix: Add `skip: int = 0, limit: int = 100` to method signature and apply in query  

📚 LEARNINGS (compressed):  
1. [high] Always include `updated_at` with `onupdate=func.now()`  
2. [high] Index all FKs and frequent query columns  
3. [high] Use `Numeric` for scores/confidence levels  
4. [high] Prevent N+1 with explicit eager loading  
5. [high] Paginate all list endpoints to prevent memory overload