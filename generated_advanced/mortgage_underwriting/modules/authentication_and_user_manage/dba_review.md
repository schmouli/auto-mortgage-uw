⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `users` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to model.

Issue 2: **Email column missing index**  
> Fix: Add `__table_args__ = (Index('ix_users_email', 'email'),)` to `User` model for performance.

Issue 3: **Foreign key `role_id` missing `ondelete` parameter**  
> Fix: Update ForeignKey to: `ForeignKey("roles.id", ondelete="SET NULL")` (or appropriate constraint).

Issue 4: **Relationship `UserRole.role` uses old-style definition without Mapped type hint**  
> Fix: Use `role: Mapped["Role"] = relationship("Role", back_populates="user_roles")`.

Issue 5: **Service method `get_users()` does not implement pagination (skip/limit)**  
> Fix: Add `skip: int = 0, limit: int = 100` parameters and apply to query with `.offset().limit()`.

Issue 6: **No composite index for common query pattern: `email + is_active`**  
> Fix: Add `Index('ix_users_email_is_active', 'email', 'is_active')` to `__table_args__`.

---

📚 LEARNINGS (compressed):  
1. [high] Always include `updated_at` with `onupdate=func.now()` for auditability  
2. [high] Index all lookup fields including email, foreign keys, and status flags  
3. [high] Prefer `SET NULL` or `CASCADE` for explicit FK behavior – never omit `ondelete`  
4. [high] Use `Mapped[T]` and `back_populates=` for bidirectional SQLAlchemy 2.0+ relationships  
5. [high] Paginate all list endpoints to prevent memory exhaustion and slow queries