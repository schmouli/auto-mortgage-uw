⚠️ BLOCKED  
Issue 1: **Missing composite index on `email` + `is_active`**  
&nbsp;&nbsp;&nbsp;&nbsp;🔍 Found `email` column used in filters alongside `is_active`, but no composite index defined.  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 Fix: Add `Index('ix_client_email_active', 'email', 'is_active')` to optimize query performance.

Issue 2: **Float used for `annual_income` field**  
&nbsp;&nbsp;&nbsp;&nbsp;🔍 Column `annual_income` uses `Float` instead of `Numeric(19, 4)`  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 Fix: Change type to `sa.Numeric(19, 4)` and generate new migration

Issue 3: **Foreign key `client_id` missing `ondelete` parameter**  
&nbsp;&nbsp;&nbsp;&nbsp;🔍 In `Application` model, `client_id` FK does not define `ondelete` behavior  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 Fix: Specify `ondelete="CASCADE"` or appropriate constraint per business logic

Issue 4: **Lazy-loading relationship may cause N+1 in `Client.applications`**  
&nbsp;&nbsp;&nbsp;&nbsp;🔍 Relationship lacks `lazy="selectin"` or explicit `joinedload()` in service layer  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 Fix: Annotate with `Mapped[list["Application"]]` and ensure services use `selectinload(Client.applications)`

Issue 5: **List retrieval method missing pagination (`skip`, `limit`)**  
&nbsp;&nbsp;&nbsp;&nbsp;🔍 Service method `get_clients()` performs unbounded SELECT *  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 Fix: Add `skip: int = 0, limit: int = 100` params, apply `.offset().limit()` in query

---

📚 LEARNINGS (compressed):  
1. [high] Always add composite indexes for multi-column access patterns like `(email, is_active)`  
2. [high] Never use `float` for money – switch to `Decimal(19, 4)`  
3. [high] All FKs must declare `ondelete`; default to `RESTRICT` unless cascading is intended  
4. [high] Prevent N+1 by using `selectinload()` or `joinedload()` when querying related data  
5. [high] Enforce max page size (`limit <= 100`) on all paginated endpoints  

✅ Once fixed, rerun validation.