⚠️ BLOCKED  
Issue 1: **Missing updated_at field** on `document_uploads` table  
Issue 2: **Foreign key missing ondelete specification** on `application_id` in `documents` table  
Issue 3: **No index on `uploaded_by` foreign key column** in `document_uploads` table  
Issue 4: **Float used for `file_size_kb`** — violates financial/data precision rule (should be Integer or Decimal if fractional)  
Issue 5: **Missing composite index** for common query pattern: `(application_id, document_type)`  

---

### 🔧 Fix Guidance

#### 1. **Add `updated_at` to `document_uploads`**
```python
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), 
    onupdate=func.now(),
    nullable=False
)
```

#### 2. **Specify `ondelete` for Foreign Keys**
```python
application_id: Mapped[int] = mapped_column(
    ForeignKey("applications.id", ondelete="CASCADE"),
    nullable=False
)
```

#### 3. **Index `uploaded_by` and other FKs**
```python
Index('ix_document_uploads_uploaded_by', 'uploaded_by'),
Index('ix_documents_application_id', 'application_id'),
```

#### 4. **Change `file_size_kb` from Float to Integer**
```python
file_size_kb: Mapped[int] = mapped_column(Integer, nullable=False)
```

#### 5. **Add Composite Index**
```python
Index('ix_documents_app_doc_type', 'application_id', 'document_type')
```

---

✅ After applying fixes, revalidate with:
```bash
uv run alembic revision --autogenerate -m "fix_schema_issues"
uv run alembic upgrade head
```

📚 LEARNINGS:
- Always include both `created_at` and `updated_at` with timezone-aware types
- Foreign keys must define `ondelete` to prevent orphaned rows and ensure referential integrity
- Indexes must cover not just individual columns but also common query combinations
- Never use `float` for any numeric value that could represent money or precise units

Let me know when you’ve applied these changes and I’ll re-review.