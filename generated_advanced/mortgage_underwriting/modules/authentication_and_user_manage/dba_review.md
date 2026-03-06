⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `User` table**  
> The `User` model is missing the mandatory `updated_at` column with `onupdate=func.now()` and timezone-aware `DateTime(timezone=True)`. This violates audit requirements.  

🔧 Fix: Add the following to the `User` model:
```python
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=lambda: datetime.now(timezone.utc),
    onupdate=lambda: datetime.now(timezone.utc),
    nullable=False,
)
```

---

Issue 2: **Missing composite index on `email` + `is_active`**  
> Common authentication queries filter by both email and active status. A composite index improves performance significantly.  

🔧 Fix: Add this to the `User` model’s `__table_args__`:
```python
Index('ix_user_email_is_active', 'email', 'is_active')
```

---

Issue 3: **Foreign key `role_id` missing `ondelete` policy**  
> In `UserRole`, the `role_id` ForeignKey does not specify an `ondelete` action (e.g., `"CASCADE"` or `"SET NULL"`), which can lead to orphaned rows or constraint violations.  

🔧 Fix: Update ForeignKey definition:
```python
role_id: Mapped[int] = mapped_column(
    ForeignKey("roles.id", ondelete="CASCADE"),
    nullable=False
)
```

---

Issue 4: **Lazy-loading relationship may cause N+1 queries**  
> The `roles` relationship in `User` uses default lazy loading. Without explicit eager loading (`selectinload` or `joinedload`) in service layers, it causes N+1 query issues during bulk reads.  

🔧 Fix: Either annotate as `lazy="selectin"` in the relationship or ensure all fetching in services includes:
```python
stmt = select(User).options(selectinload(User.roles))
```

---

Issue 5: **No pagination enforced in `get_users` service method**  
> Service methods like `get_users()` do not enforce a limit or skip pattern, risking unbounded result sets.  

🔧 Fix: Enforce limit/offset in service function signature and SQL query:
```python
async def get_users(..., skip: int = 0, limit: int = 100):
    ...
    stmt = select(User).offset(skip).limit(min(limit, 100))
```

---

📚 LEARNINGS (Compressed):  
1. [high] Always include `updated_at` with `onupdate` in all models  
2. [high] Composite indexes prevent slow auth queries (`email + is_active`)  
3. [high] All FKs must define `ondelete` behavior explicitly  
4. [med] Prevent N+1 via `selectinload()` or `joinedload()` in related fetches  
5. [high] Paginate all list endpoints with `skip`/`limit` and cap at 100  

✅ Once fixed, revalidate with full checklist.