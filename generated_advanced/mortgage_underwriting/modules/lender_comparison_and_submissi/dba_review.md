⚠️ BLOCKED  
Issue 1: **Missing updated_at field** on `LenderRate` table — violates audit integrity requirement  
**Fix:** Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())`  

Issue 2: **Float used for rate columns** (`prime_rate`, `posted_rate`) in `LenderRate` model  
**Fix:** Replace `Float` with `Numeric(19, 4)` for all financial rate fields  

Issue 3: **Missing composite index** on `LenderSubmission.lender_id` and `LenderSubmission.created_at` — impacts query performance for time-series lender reports  
**Fix:** Add `Index('ix_lender_submission_lender_created', 'lender_id', 'created_at')`  

Issue 4: **Unidirectional relationship** in `LenderSubmission.lender_rate_id` → `LenderRate` lacks `back_populates`  
**Fix:** Define `back_populates="lender_submissions"` on both sides of the relationship  

Issue 5: **No pagination logic in service layer** for `/lender-comparison/submissions/` endpoint  
**Fix:** Update service method to accept `skip`/`limit` and apply `offset`/`limit` in SQL query  

---

📚 LEARNINGS (compressed):  
1. [high] Always include `updated_at` with `onupdate=func.now()` for audit trails  
2. [high] Never use `Float` for rates or monetary values — use `Decimal(19,4)`  
3. [high] Composite indexes prevent full-table scans on multi-key filters  
4. [high] Bidirectional relationships with `Mapped[...]` and `back_populates` ensure ORM consistency  
5. [high] Pagination prevents memory exhaustion in list views — enforce max limit = 100