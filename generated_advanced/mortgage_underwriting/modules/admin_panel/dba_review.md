⚠️ BLOCKED  
Issue 1: **Missing updated_at field** on `AdminUser` table  
Issue 2: **Float used for `hourly_rate` column** in `SupportAgent` table (violates financial precision rule)  
Issue 3: **Foreign key `role_id` missing `ondelete` parameter** in `AdminUser` table  
Issue 4: **No composite index** on (`email`, `is_active`) despite common query pattern  
Issue 5: **Lazy-loaded relationship** detected in `AdminUser.roles` without documented eager loading  
Issue 6: **List service method missing pagination** for admin user listing  

---

### 🔍 Detailed Findings & Fixes

#### Issue 1: Missing `updated_at` Field
- **Location**: `models.AdminUser`
- **Problem**: Table lacks `updated_at` audit column which is mandatory per project standards.
- **Fix**:
  ```python
  updated_at: Mapped[datetime] = mapped_column(
      DateTime(timezone=True),
      default=lambda: datetime.now(timezone.utc),
      onupdate=lambda: datetime.now(timezone.utc)
  )
  ```

#### Issue 2: Float Used for Monetary Value
- **Location**: `models.SupportAgent.hourly_rate`
- **Problem**: Column defined as `Float` instead of `Numeric(19, 4)`
- **Fix**:
  ```python
  hourly_rate: Mapped[Decimal] = mapped_column(Numeric(19, 4))
  ```

#### Issue 3: Foreign Key Missing `ondelete`
- **Location**: `models.AdminUser.role_id`
- **Problem**: Does not specify `ondelete=` behavior
- **Fix**:
  ```python
  role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
  ```

#### Issue 4: Missing Composite Index
- **Query Pattern Observed**: Filtering by `email` and `is_active` together
- **Problem**: No index exists for this combination
- **Fix**:
  ```python
  __table_args__ = (
      Index('ix_admin_user_email_is_active', 'email', 'is_active'),
  )
  ```

#### Issue 5: Lazy-loaded Relationship Risking N+1
- **Location**: `models.AdminUser.roles`
- **Problem**: Defined without explicit `lazy="selectin"` or documented use of `selectinload()` in service layer
- **Fix Options**:
  - Option A: Define with `lazy="selectin"`:
    ```python
    roles: Mapped[List["Role"]] = relationship("Role", back_populates="admin_users", lazy="selectin")
    ```
  - Option B: Ensure all fetching uses `selectinload()` in service methods

#### Issue 6: List Endpoint Lacks Pagination
- **Location**: Service function retrieving `list_admin_users`
- **Problem**: No `skip`, `limit` support; could cause performance issues
- **Fix Example**:
  ```python
  async def list_admin_users(session: AsyncSession, *, skip: int = 0, limit: int = 100):
      stmt = select(AdminUser).offset(skip).limit(min(limit, 100))
      result = await session.execute(stmt)
      return result.scalars().all()
  ```

---

📚 LEARNINGS (Compressed Summary):

1. Always include both `created_at` and `updated_at` fields with timezone-aware datetimes.
2. Never use `float` for money – always prefer `Decimal(19, 4)` or equivalent.
3. Specify `ondelete` policy for all foreign keys (`CASCADE`, `SET NULL`, or `RESTRICT`)
4. Add composite indexes where queries filter on multiple columns together
5. Prevent N+1 via `selectinload()` or setting `lazy="selectin"` in relationship definition
6. Paginate all list endpoints with `skip`/`limit` (max 100 per page)

✅ Once fixed, re-run validation.