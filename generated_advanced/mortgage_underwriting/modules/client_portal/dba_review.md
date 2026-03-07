⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `clients` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), onupdate=func.now())` to match audit requirements.

Issue 2: **Email column missing index** (`ix_clients_email`)  
> Fix: Add `Index('ix_clients_email', 'email')` for efficient lookups and login queries.

Issue 3: **Foreign key `user_id` missing `ondelete` policy**  
> Fix: Specify `ondelete="CASCADE"` or appropriate rule in ForeignKey definition.

Issue 4: **Relationship `applications` defined without `Mapped` type hint**  
> Fix: Update to `applications: Mapped[List["Application"]] = relationship(..., back_populates="client")`

Issue 5: **No pagination enforced in service layer for client listing**  
> Fix: Add `skip: int`, `limit: int` params (max 100) and apply in query using `.offset().limit()`

Issue 6: **N+1 risk detected: `applications` relationship is lazy-loaded without eager loading strategy documented in services**  
> Fix: In services, load with `selectinload(client.applications)` where needed.

---

📚 LEARNINGS (compressed):  
1. [high] Always include `updated_at` with `onupdate=func.now()` for audit compliance  
2. [high] Index all lookup columns like `email` to prevent slow queries  
3. [high] Use `Mapped[...]` syntax for SQLAlchemy 2.0+ relationships  
4. [high] Enforce service-level pagination on all list endpoints  
5. [high] Prevent N+1 by documenting eager loading strategies (e.g., `selectinload`)  

🔁 RETRY with fixes applied. Re-run validation after Alembic revision.