⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `users` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to the `User` model.

Issue 2: **Email column missing index** (`ix_users_email`)  
> Fix: Add `__table_args__ = (Index('ix_users_email', 'email'),)` to `User` model to support efficient lookups.

Issue 3: **Foreign key `role_id` in `users` table missing `ondelete` parameter**  
> Fix: Update ForeignKey definition to include `ondelete="SET NULL"` or appropriate constraint:  
```python
role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
```

Issue 4: **Old-style relationship definition detected**  
> Fix: Replace `relationship("Role")` with `Mapped["Role"] = relationship("Role", back_populates="users")` and ensure `Role` has corresponding `Mapped[List["User"]] = relationship("User", back_populates="role")`.

Issue 5: **No pagination implemented in user listing service/query**  
> Fix: Ensure services use `skip`, `limit` parameters with a maximum of 100 rows returned per page, e.g.:  
```python
stmt = select(User).offset(skip).limit(min(limit, 100))
```

📚 LEARNINGS (compressed):  
1. [high] Always define both `created_at` and `updated_at` with timezone-aware types and auto-update triggers  
2. [high] Index all lookup-sensitive fields like `email`, especially when used in auth filters  
3. [high] Prefer explicit `ondelete` behavior for referential integrity  
4. [high] Use SQLAlchemy 2.0+ `Mapped[T]` annotations for static analysis and clarity  
5. [high] Prevent N+1 via documented eager loading strategies (`selectinload`, `joinedload`)  

🔁 RETRY AFTER FIXING ABOVE ISSUES