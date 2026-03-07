⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `admin_action_log` table**  
- Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())`  

Issue 2: **Email column in `admin_users` missing index**  
- Fix: Add `Index('ix_admin_users_email', 'email')`  

Issue 3: **Foreign key `admin_role_id` in `admin_users` missing `ondelete` parameter**  
- Fix: Update to `ForeignKey("admin_roles.id", ondelete="SET NULL")`  

Issue 4: **N+1 risk in `admin_user.roles` relationship due to lazy loading**  
- Fix: Annotate with `selectinload()` in service queries or set `lazy="selectin"` in relationship definition  

Issue 5: **No pagination enforced in `get_admin_users` service method**  
- Fix: Add `skip: int`, `limit: int` params (max 100), apply `.offset().limit()` in query  

📚 LEARNINGS (compressed):  
1. [high] Always pair `created_at` with `updated_at` including `onupdate=func.now()`  
2. [high] Index all FKs and high-query columns like email  
3. [high] Enforce `ondelete` behavior for referential integrity  
4. [high] Prevent N+1 via `selectinload()` or `joinedload()`  
5. [high] Paginate all list endpoints (`skip`, `limit`) max 100 per page