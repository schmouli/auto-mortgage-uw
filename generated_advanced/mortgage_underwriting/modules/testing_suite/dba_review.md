⚠️ BLOCKED  
Issue 1: **Float used for financial values** in `test_result` table (`confidence_score FLOAT`) — violates mandatory Decimal requirement.  
**Fix:** Change to `Numeric(19, 4)`.

Issue 2: **Missing composite index** on `test_run` table for common query pattern `(suite_id, status)` — may cause slow queries in reporting.  
**Fix:** Add `Index('ix_test_run_suite_status', 'suite_id', 'status')`.

Issue 3: **N+1 query risk** in `TestSuite.tests` relationship — lazy loading will trigger repeated DB hits.  
**Fix:** Update service layer to use `selectinload(TestSuite.tests)` for batch fetching.

Issue 4: **No pagination** enforced in `list_test_suites()` service method — unbounded query can lead to memory exhaustion.  
**Fix:** Add `skip: int`, `limit: int` params with max limit = 100.

---

📚 LEARNINGS (compressed):  
1. [high] Always use `Decimal(19, 4)` for financial values — never `float`.  
2. [high] Define composite indexes like `Index('ix_col1_col2', 'col1', 'col2')` for multi-column queries.  
3. [high] Prevent N+1 with explicit eager loading via `selectinload()` or `joinedload()`.  
4. [high] Enforce `skip`/`limit` (<100) in all list endpoints to prevent performance degradation.