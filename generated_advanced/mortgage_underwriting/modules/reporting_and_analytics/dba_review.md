⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `report` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to the `Report` model.

Issue 2: **Float used for `total_value` and `average_ltv` in `portfolio_summary` table**  
> Fix: Replace `Float` with `Numeric(19, 4)` for all financial fields. Example:  
```python
total_value = Column(Numeric(19, 4), nullable=False)
```

Issue 3: **Missing composite index on frequently queried pair (`generated_by`, `report_type`) in `report` table**  
> Fix: Add composite index in `__table_args__`:  
```python
__table_args__ = (Index('ix_report_generated_by_type', 'generated_by', 'report_type'),)
```

Issue 4: **Unidirectional relationship in `Report` model referencing `User` without `back_populates`**  
> Fix: Ensure both sides of the relationship define `back_populates`. Update as follows:
```python
generated_by_user: Mapped["User"] = relationship("User", back_populates="reports")
```

Issue 5: **No pagination implemented in `get_reports_list()` service method**  
> Fix: Add `skip: int`, `limit: int` parameters (enforce max 100) and apply to query:
```python
query = select(Report).offset(skip).limit(min(limit, 100))
```

---

📚 LEARNINGS (compressed):  
1. [high] Always use `Decimal(19,4)` for financial data — never `float`  
2. [high] All tables require `created_at` and `updated_at` with timezone-aware timestamps  
3. [high] Composite indexes prevent full-table scans on multi-column filters  
4. [high] Bidirectional relationships must use `Mapped[T]` and `back_populates`  
5. [high] List endpoints must implement pagination via `offset`/`limit` with enforced maximum size