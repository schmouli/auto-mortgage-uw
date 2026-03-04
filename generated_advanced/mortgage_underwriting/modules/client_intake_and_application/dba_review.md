⚠️ BLOCKED  
Issue 1: **Missing updated_at field with onupdate=func.now()** on `application_documents` table.  
Issue 2: **Float used for financial value** in `estimated_income` column (`clients` table) — violates Decimal requirement.  
Issue 3: **Foreign key missing ondelete behavior** in `client_id` ForeignKey of `applications` table.  
Issue 4: **No composite index** on `(client_id, status)` in `applications` table — common query pattern.  
Issue 5: **Missing pagination** in `get_applications_list()` service method — unbounded SELECT * risk.

---

### 🛠 Fix Guidance

#### Issue 1: Add `updated_at` to `application_documents`
```python
# In models.py
from sqlalchemy import func
from datetime import datetime

class ApplicationDocument(Base):
    ...
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
```

#### Issue 2: Convert `estimated_income` from Float to Decimal
```python
# Before
estimated_income = Column(Float)

# After
estimated_income: Mapped[Decimal] = mapped_column(
    Numeric(19, 4),
    nullable=False
)
```

#### Issue 3: Add `ondelete` to ForeignKey
```python
# Before
client_id = Column(Integer, ForeignKey("clients.id"))

# After
client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"))
```

#### Issue 4: Add composite index for frequent query pattern
```python
# In models.py near Applications class
class Application(Base):
    ...

__table_args__ = (
    Index('ix_applications_client_status', 'client_id', 'status'),
)
```

#### Issue 5: Implement pagination in service
```python
# In services.py
async def get_applications_list(db: AsyncSession, *, skip: int = 0, limit: int = 100):
    stmt = select(Application).offset(skip).limit(min(limit, 100))
    result = await db.execute(stmt)
    return result.scalars().all()
```

---

✅ Once these fixes are applied, re-run validation.  
📚 LEARNINGS (applied here):  
1. Always use `Decimal` for money (`Numeric(19,4)`)  
2. Include `updated_at` with `onupdate=func.now()` on all tables  
3. Specify `ondelete` behavior for referential integrity  
4. Create indexes for performance-critical query paths  
5. Paginate all list endpoints to prevent resource exhaustion