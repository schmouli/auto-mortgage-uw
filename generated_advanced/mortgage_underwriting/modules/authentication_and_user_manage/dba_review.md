⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `user_sessions` table**  
> Fix: Add `updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())` to model.

Issue 2: **Email column missing index in `users` table**  
> Fix: Add `__table_args__ = (Index('ix_users_email', 'email'),)` to the `User` model.

Issue 3: **Foreign key `user_id` in `user_sessions` lacks `ondelete` parameter**  
> Fix: Update foreign key to: `ForeignKey("users.id", ondelete="CASCADE")`

Issue 4: **No composite index for common query pattern (e.g., `email` + `is_active`) in `users` table**  
> Fix: Add `Index('ix_users_email_active', 'email', 'is_active')` inside `__table_args__`.

Issue 5: **Lazy-loaded relationship `sessions` in `User` model may cause N+1 queries**  
> Fix: In service layer, use `selectinload(User.sessions)` when querying users with sessions.

---

📚 LEARNINGS (compressed):  
1. [high] Always include `updated_at` with `onupdate=func.now()`  
2. [high] Index all FKs and frequently queried fields (`email`, `is_active`)  
3. [high] Specify `ondelete` for all foreign keys  
4. [high] Composite indexes prevent slow multi-column lookups  
5. [high] Eager load relationships via `selectinload()` or `joinedload()` to prevent N+1