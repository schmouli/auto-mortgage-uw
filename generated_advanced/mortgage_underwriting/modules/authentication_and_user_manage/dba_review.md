⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `users` table**  
> The `User` model is missing the mandatory `updated_at` audit field. Every table must include `created_at` and `updated_at` as per regulatory and project standards.  
🔧 Fix: Add `updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to the `User` model.

Issue 2: **Email column missing index**  
> The `email` column in the `users` table does not have an index, which is required for efficient lookups and authentication performance.  
🔧 Fix: Add `Index('ix_users_email', 'email')` to the `User` model to ensure fast querying by email.

Issue 3: **Foreign key constraints missing `ondelete` parameter**  
> In the `UserSession` model, the foreign key to `user_id` does not define an `ondelete` behavior. All foreign keys must explicitly set `ondelete` to ensure data integrity.  
🔧 Fix: Update the `user_id` foreign key to include `ondelete="CASCADE"` (or appropriate rule based on business logic).

Issue 4: **Unidirectional relationship in `UserSession`**  
> The `UserSession` model defines a relationship to `User`, but `back_populates` is missing from both sides. This can lead to inconsistent object state and N+1 issues.  
🔧 Fix: Ensure both `User.sessions` and `UserSession.user` relationships define `back_populates` to maintain bidirectionality.

Issue 5: **No documented eager loading in service layer for user sessions**  
> Queries fetching users along with sessions may trigger N+1 queries due to lazy-loading unless explicitly handled via `selectinload()` or `joinedload()`.  
🔧 Fix: In `services.py`, annotate session fetches with `selectinload(User.sessions)` where applicable to prevent performance degradation.

---

✅ APPROVED (once above fixes are implemented)