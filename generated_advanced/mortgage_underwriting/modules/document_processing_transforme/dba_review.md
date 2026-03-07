⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `document` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to the `Document` model.

Issue 2: **Float used for `confidence_score` in `document_analysis` table**  
> Fix: Change `Float` to `Numeric(19, 4)` for all financial or score decimal fields to ensure precision.

Issue 3: **Missing composite index on `client_id` and `status` in `document` table**  
> Fix: Add `__table_args__ = (Index('ix_document_client_status', 'client_id', 'status'),)` to `Document` model for optimized filtering.

Issue 4: **Foreign key `document_type_id` missing `ondelete` policy**  
> Fix: Update ForeignKey definition to include `ondelete="RESTRICT"` or appropriate constraint, e.g., `ForeignKey("document_type.id", ondelete="RESTRICT")`.

Issue 5: **Old-style relationship in `DocumentType` model (`documents` relationship)**  
> Fix: Replace with SQLAlchemy 2.0+ Mapped pattern:  
```python
documents: Mapped[List["Document"]] = relationship("Document", back_populates="document_type")
```

Issue 6: **No pagination enforced in `get_documents()` service method**  
> Fix: Add `skip: int = 0, limit: int = 100` parameters and apply `.offset().limit()` in query.

---

📚 LEARNINGS (compressed):  
1. [high] Always include both `created_at` and `updated_at` with timezone-aware types  
2. [high] Never use `Float` for scores or financial data—use `Decimal`  
3. [med] Composite indexes prevent full-table scans on multi-field filters  
4. [high] Foreign keys need explicit `ondelete` policies for referential integrity  
5. [high] Use SQLAlchemy 2.0+ `Mapped` syntax for bidirectional relationships  
6. [high] Enforce pagination (`skip`, `limit`) on all list queries to avoid memory overloads