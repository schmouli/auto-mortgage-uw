⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `TestRun` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), onupdate=func.now())` to model.

Issue 2: **Foreign key in `TestCase` missing `ondelete` parameter**  
> Fix: Update `ForeignKey("test_suite.id")` → `ForeignKey("test_suite.id", ondelete="CASCADE")`

Issue 3: **N+1 query risk in `TestSuite.tests` relationship**  
> Fix: Annotate service method with `selectinload(TestSuite.tests)` for eager loading

Issue 4: **No pagination implemented in `list_test_suites` service method**  
> Fix: Add `(skip: int = 0, limit: int = 100)` params and apply to query

Issue 5: **Email column in `Tester` table lacks index**  
> Fix: Add `Index('ix_tester_email', 'email')` for performance

📚 LEARNINGS (compressed):  
1. [high] Always define `updated_at` with `onupdate=func.now()`  
2. [high] Specify `ondelete` for all foreign keys (`CASCADE`, `SET NULL`, or `RESTRICT`)  
3. [high] Prevent N+1 with `selectinload()` or `joinedload()`  
4. [high] Paginate all list endpoints (`skip`, `limit` with max 100)  
5. [high] Index all lookup columns like email, status, etc.