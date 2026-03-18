⚠️ BLOCKED  
Issue 1: **Missing `updated_at` field** in one or more models — every table must have both `created_at` and `updated_at` with `onupdate=func.now()`  
Issue 2: **Foreign key constraints missing `ondelete` parameter** — all `ForeignKey` declarations must specify `ondelete="CASCADE"`, `SET NULL`, or `RESTRICT`  
Issue 3: **Relationships not using SQLAlchemy 2.0+ Mapped syntax** — all relationships must be declared with `Mapped["Class"]` and include `back_populates`  
Issue 4: **No pagination enforced in list queries** — service layer must implement `skip`/`limit` with a maximum of 100  

📚 LEARNINGS (compressed):  
1. [high] Always include `updated_at` with `onupdate=func.now()`  
2. [high] Specify `ondelete` for all foreign keys  
3. [high] Use `Mapped[T]` and `back_populates` for relationships  
4. [high] Enforce pagination (`limit <= 100`) on all list endpoints  

🔧 Fix Guidance:  
- Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to all models  
- Update FKs: `ForeignKey("table.id", ondelete="CASCADE")`  
- Refactor relationships: `relationship("Class", back_populates="attr")` with `Mapped["Class"]` type hints  
- In services, add `skip: int`, `limit: int = Query(100, le=100)` and apply in query execution  

Please provide the actual `models.py` content for detailed line-by-line review.