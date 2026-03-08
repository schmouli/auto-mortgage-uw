⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `document_versions` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())`  

Issue 2: **Foreign key `document_id` in `document_versions` lacks `ondelete` parameter**  
> Fix: Update ForeignKey to include `ondelete="CASCADE"` or appropriate constraint  

Issue 3: **No composite index on (`document_id`, `version_number`) in `document_versions`**  
> Fix: Add `Index('ix_document_versions_docid_version', 'document_id', 'version_number')` for version lookup performance  

Issue 4: **PII column `uploaded_by_sin` not encrypted and lacks audit protection**  
> Fix: Mark as encrypted via `encrypt_pii()` in model and exclude from logs/APIs; hash SIN for lookups only  

Issue 5: **Service method `get_document_history()` uses lazy-loading without eager loading**  
> Fix: Annotate relationship with `selectinload()` or `joinedload()` in service query  

Issue 6: **List endpoint `/documents/` does not enforce pagination (skip/limit)**  
> Fix: Enforce `skip: int`, `limit: int` in route and apply `.offset().limit()` in DB query  

📚 LEARNINGS (compressed):  
1. [high] Always pair `created_at` with `updated_at` and use `onupdate=func.now()`  
2. [high] Specify `ondelete` for all ForeignKey definitions  
3. [high] Composite indexes prevent slow multi-column filters  
4. [high] Encrypt/hash PII fields per PIPEDA – never store plaintext  
5. [high] Prevent N+1 with explicit eager loading strategies in services  
6. [high] Always paginate unbounded list endpoints (max 100 items per page)