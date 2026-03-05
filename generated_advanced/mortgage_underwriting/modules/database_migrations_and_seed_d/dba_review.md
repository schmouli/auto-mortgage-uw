⚠️ BLOCKED  
Issue 1: **Missing composite index** on `email` + `is_active` columns for optimized login/lookup queries.  
> 🔧 Fix: Add `Index('ix_user_email_active', 'email', 'is_active')` to the `users` table model.

Issue 2: **Float used for interest_rate column** in `loan_products` table instead of `Decimal`.  
> 🔧 Fix: Change column definition to `interest_rate = Column(Numeric(19, 4), nullable=False)`.

Issue 3: **N+1 query risk detected** — `client_applications` relationship not eagerly loaded in `get_client_with_applications()` service method.  
> 🔧 Fix: Use `selectinload(Client.applications)` when querying the client in the service layer.

Issue 4: **Missing pagination in list_users endpoint** — currently allows unlimited fetch.  
> 🔧 Fix: Enforce `skip: int`, `limit: int` parameters with `limit <= 100` and apply `.offset().limit()` in query.

Issue 5: **Foreign key constraint missing `ondelete` clause** in `user_sessions.user_id` referencing `users.id`.  
> 🔧 Fix: Update to `ForeignKey("users.id", ondelete="CASCADE")`.

---

📚 LEARNINGS (compressed):  
1. [high] Always define composite indexes like `Index('ix_col1_col2', 'col1', 'col2')` for frequent multi-field queries  
2. [high] Never use `float` for money – enforce `Numeric(19,4)` across all financial fields  
3. [high] Prevent N+1 by using `selectinload()` or `joinedload()` in services for related data access  
4. [high] Paginate all list endpoints with `skip`/`limit` and enforce `limit <= 100`  
5. [high] All `ForeignKey` definitions must include `ondelete=` to ensure safe cascading behavior