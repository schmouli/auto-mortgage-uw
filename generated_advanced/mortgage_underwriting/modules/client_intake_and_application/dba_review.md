⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `client_intake` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to model.

Issue 2: **Email column missing index** (`ix_client_email` not found)  
> Fix: Add `Index('ix_client_email', 'email')` to ensure performant lookups by email.

Issue 3: **Foreign key `application.client_id` missing `ondelete` policy**  
> Fix: Update ForeignKey definition to include `ondelete="CASCADE"` or appropriate constraint.

Issue 4: **Relationships use old-style syntax without Mapped types**  
> Example: `client = relationship("Client")`  
> Fix: Replace with `client: Mapped["Client"] = relationship("Client", back_populates="applications")`

Issue 5: **No selectinload/joinedload pattern documented in service layer for related entities**  
> Risk of N+1 queries when accessing `client.applications`.  
> Fix: Document and enforce eager loading via `selectinload(Client.applications)` in query builder.

Issue 6: **List endpoint in service does not implement pagination (skip/limit)**  
> Will lead to unbounded result sets.  
> Fix: Add `skip: int = 0`, `limit: int = 100` parameters to method signature and apply `.offset().limit()` in query.

---

🛠 Summary Fixes Required:
```python
# In models.py
class Client(Base):
    __tablename__ = 'clients'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String, unique=True, index=True)  # <-- add index
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Application(Base):
    client_id = Column(UUID(as_uuid=True), ForeignKey('clients.id', ondelete='CASCADE'))  # <-- add ondelete
    client: Mapped["Client"] = relationship("Client", back_populates="applications")  # <-- Mapped + back_populates

# In services.py
async def list_applications(..., skip: int = 0, limit: int = 100):
    stmt = select(Application).offset(skip).limit(min(limit, 100))
```

✅ Once above are addressed, revalidate.