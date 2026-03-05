⚠️ BLOCKED  
Issue 1: **Missing updated_at field with onupdate=func.now()** on `application_lenders` table.  
Issue 2: **Foreign key missing ondelete specification** in `applications.client_id` (`ForeignKey("clients.id")`).  
Issue 3: **Missing index on email column** in `clients.email`.  
Issue 4: **Float used for financial value** in `applications.loan_amount` (type: `Float`).  
Issue 5: **No pagination enforced in service layer** for application listing endpoints.  

---

### 🔧 Fix Guidance

#### Issue 1: Missing `updated_at` field
Add to **every model** including `application_lenders`:
```python
from sqlalchemy import func
from sqlalchemy.orm import mapped_column
from datetime import datetime

updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    default=func.now(),
    onupdate=func.now(),
    nullable=False
)
```

#### Issue 2: Foreign key without `ondelete`
Update `applications.client_id`:
```python
client_id: Mapped[int] = mapped_column(
    ForeignKey("clients.id", ondelete="CASCADE"),
    nullable=False
)
```

#### Issue 3: Missing index on `clients.email`
Add index:
```python
email: Mapped[str] = mapped_column(String, unique=True, index=True)
```

#### Issue 4: Float used for financial value
Change `applications.loan_amount` from `Float` to:
```python
loan_amount: Mapped[Decimal] = mapped_column(
    Numeric(19, 4),
    nullable=False
)
```

#### Issue 5: No pagination in services
In service methods returning lists:
```python
async def get_applications(skip: int = 0, limit: int = 100):
    stmt = select(Application).offset(skip).limit(min(limit, 100))
    result = await session.execute(stmt)
    return result.scalars().all()
```

Apply fixes across all related models and update Alembic migrations accordingly.

📚 LEARNINGS RECAP:
- Always use `Numeric(19,4)` for money.
- Index frequently queried fields like `email`.
- Specify `ondelete` behavior for all foreign keys.
- Enforce `updated_at` with `onupdate=func.now()` in all tables.
- Paginate all list endpoints with configurable but capped limits.