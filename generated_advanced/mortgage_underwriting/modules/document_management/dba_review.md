⚠️ BLOCKED  
Issue 1: **Missing `updated_at` field** on the `Document` model — violates Timestamp Integrity rule.  
Issue 2: **Foreign key `application_id` missing `ondelete` parameter** — violates Foreign Key Constraints rule.  
Issue 3: **No indexes defined** on frequently queried fields such as `application_id`, `uploaded_by`, and `document_type` — violates Indexes for Performance rule.  
Issue 4: **Relationships not using Mapped syntax** — violates Relationship Patterns (SQLAlchemy 2.0+) rule.  

---

### 🔧 Fix Guidance

#### 1. Add `updated_at` to `Document` model
```python
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    onupdate=func.now(),
    nullable=False,
)
```

#### 2. Add `ondelete` to `application_id` foreign key
```python
application_id: Mapped[UUID] = mapped_column(
    ForeignKey("applications.id", ondelete="CASCADE"),
    nullable=False,
    index=True
)
```

#### 3. Add required indexes
```python
__table_args__ = (
    Index('ix_documents_application_id', 'application_id'),
    Index('ix_documents_uploaded_by', 'uploaded_by'),
    Index('ix_documents_document_type', 'document_type'),
)
```

#### 4. Update relationships to use `Mapped` syntax
Example:
```python
application: Mapped["Application"] = relationship(
    "Application",
    back_populates="documents"
)
```

Once these changes are applied, revalidate.  
Ensure services implement pagination (`skip`, `limit`) for listing documents.

📚 LEARNINGS (compressed):  
1. Always include audit fields (`created_at`, `updated_at`)  
2. Specify `ondelete` for all foreign keys  
3. Index all FKs and filterable columns  
4. Use SQLAlchemy 2.0+ `Mapped` types for relationships  
5. Add pagination for all list endpoints