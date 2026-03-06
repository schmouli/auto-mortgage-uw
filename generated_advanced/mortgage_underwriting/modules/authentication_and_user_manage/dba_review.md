⚠️ BLOCKED  
Issue 1: **Missing updated_at field** on `User` table  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` to model  

Issue 2: **Email column missing index**  
> Fix: Add `Index('ix_users_email', 'email')` for performant lookups  

Issue 3: **Foreign key `role_id` missing `ondelete` parameter**  
> Fix: Update ForeignKey definition to include `ondelete="SET NULL"` or appropriate constraint  

Issue 4: **Relationship `role` uses old-style syntax without Mapped type hint**  
> Fix: Replace with `role: Mapped["Role"] = relationship("Role", back_populates="users")`  

Issue 5: **No pagination enforced in service layer for user listing**  
> Fix: Ensure services accept `skip`, `limit` params and apply in SQL query (`LIMIT :limit OFFSET :skip`)  

📚 LEARNINGS (compressed):  
1. [high] Always add `updated_at` with `server_default` and `onupdate`  
2. [high] Index all lookup columns like email, foreign keys  
3. [high] Use `Mapped[...]` and `back_populates` for SQLAlchemy 2.0+  
4. [high] Specify `ondelete` for referential integrity  
5. [high] Enforce pagination in all list endpoints (`skip`, `limit`)