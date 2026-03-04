⚠️ BLOCKED  
Issue 1: **Missing `updated_at` field** on the `UserSession` table  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 *Fix*: Add `updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())`  

Issue 2: **Foreign key `user_id` in `UserSession` missing `ondelete` behavior**  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 *Fix*: Update to `ForeignKey("users.id", ondelete="CASCADE")`  

Issue 3: **Missing index on `email` column in `User` table**  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 *Fix*: Add `Index('ix_user_email', 'email')`  

Issue 4: **Missing composite index on `UserSession` for `user_id` and `expires_at`**  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 *Fix*: Add `Index('ix_user_session_user_id_expires_at', 'user_id', 'expires_at')`  

Issue 5: **No pagination implemented in user listing service method**  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 *Fix*: Modify service method to accept `skip` and `limit` parameters (enforce max `limit=100`) and apply in SQL query  

Issue 6: **N+1 risk in `roles` relationship in `User` model due to lazy loading**  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 *Fix*: Use `selectinload` or `joinedload` in service layer when fetching users with roles  

---

✅ APPROVED once above issues are resolved.  
🛠️ Recommended migration-safe refactor steps:  
1. Add new columns/indexes in additive migrations  
2. Backfill default values for `updated_at` where needed  
3. Deploy changes  
4. Create follow-up migration to enforce non-null constraints if needed  

Let me know if you'd like the corrected `models.py` or example migration files.