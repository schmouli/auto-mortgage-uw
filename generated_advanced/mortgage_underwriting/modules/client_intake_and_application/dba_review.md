⚠️ BLOCKED  
Issue 1: **Missing updated_at field with onupdate=func.now()** on the `Application` model  
Issue 2: **Foreign key `client_id` in `Application` model missing `ondelete` parameter**  
Issue 3: **No composite index** for common query pattern (e.g., `client_id` + `status`)  
Issue 4: **Email column missing index** in `Client` model  
Issue 5: **Float used for `loan_amount` and `property_value`** instead of `Numeric(19, 4)`  

---

### 🔧 Fix Guidance

#### 1. Add `updated_at` to `Application` model
```python
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    onupdate=func.now(),
    nullable=False,
)
```

#### 2. Add `ondelete` to `client_id` FK
```python
client_id: Mapped[int] = mapped_column(
    Integer,
    ForeignKey("clients.id", ondelete="CASCADE"),
    nullable=False
)
```

#### 3. Add composite index for frequent query pattern
In `Application` model:
```python
__table_args__ = (
    Index('ix_application_client_status', 'client_id', 'status'),
)
```

#### 4. Add index on `email` column in `Client` model
```python
__table_args__ = (
    Index('ix_client_email', 'email'),
)
```

#### 5. Replace `Float` with `Numeric(19, 4)` for financial fields
Update both `loan_amount` and `property_value`:
```python
loan_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
property_value: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
```

---

✅ Once the above fixes are applied, re-run validation.  
📚 Consider auto-linting models with `ruff` and validating migrations with `alembic check`.