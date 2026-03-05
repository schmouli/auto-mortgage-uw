⚠️ BLOCKED  
Issue 1: **Missing updated_at field** on `ClientPortalSession` table  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())`  

Issue 2: **Email column missing index** in `Client` model  
> Fix: Add `__table_args__ = (Index('ix_client_email', 'email'),)` to `Client` class  

Issue 3: **Foreign key constraint without ondelete** in `ClientPortalSession.client_id`  
> Fix: Update ForeignKey to: `ForeignKey("clients.id", ondelete="CASCADE")`  

Issue 4: **Float used for session_expiry_hours** in `ClientPortalSession`  
> Fix: Replace `Float` with `Numeric(5, 2)` for financial/time-based precision  

Issue 5: **No composite index for common query pattern**: `client_id + is_active`  
> Fix: Add `Index('ix_client_portal_session_client_is_active', 'client_id', 'is_active')`  

Issue 6: **Lazy-loading relationship detected** in `Client.sessions`  
> Fix: In service layer, load with `selectinload(Client.sessions)` or define as `lazy="selectin"` in relationship  

Issue 7: **List endpoints not paginated** (`get_clients`, `get_sessions`)  
> Fix: Add `skip: int = 0, limit: int = 100` parameters and apply `.offset().limit()` in query  

---

🛠 Summary of Fixes Required:
```python
# models.py additions/modifications required:

# Client model
class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        Index('ix_client_email', 'email'),
    )

# ClientPortalSession model
class ClientPortalSession(Base):
    __tablename__ = "client_portal_sessions"

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    session_expiry_hours = Column(Numeric(5, 2))  # instead of Float

    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"))
    
    __table_args__ = (
        Index('ix_client_portal_session_client_is_active', 'client_id', 'is_active'),
    )

# Relationships must be defined with Mapped and back_populates:
sessions: Mapped[List["ClientPortalSession"]] = relationship(
    "ClientPortalSession",
    back_populates="client",
    lazy="selectin"
)

# Service layer must include pagination:
def get_clients(skip: int = 0, limit: int = 100): ...
stmt = select(Client).offset(skip).limit(min(limit, 100))
```

🔁 Once above changes applied, revalidate.