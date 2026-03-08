⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `clients` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), onupdate=func.now())` to match audit requirements.

Issue 2: **Foreign key `application.client_id` missing `ondelete` parameter**  
> Fix: Update ForeignKey definition to include `ondelete="CASCADE"` or appropriate constraint.

Issue 3: **No composite index on (`email`, `is_active`) despite common query pattern**  
> Fix: Add `Index('ix_clients_email_is_active', 'email', 'is_active')` for performance.

Issue 4: **Float used for `annual_income` column in `clients` table**  
> Fix: Change column type to `Numeric(19, 4)` to enforce financial precision.

Issue 5: **Service method `list_applications()` lacks pagination support**  
> Fix: Add `skip: int`, `limit: int` params (max 100), apply in SQL query with `.offset().limit()`.

---

📚 LEARNINGS (compressed):  
1. [high] Always add `updated_at` with `onupdate=func.now()` for audit compliance  
2. [high] Specify `ondelete` behavior on all ForeignKey declarations  
3. [high] Use `Numeric(19,4)` for all financial fields – never `float`  
4. [high] Composite indexes prevent full-table scans on multi-field filters  
5. [high] Pagination mandatory on all list endpoints – prevent memory overloads