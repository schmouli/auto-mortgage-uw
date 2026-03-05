⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `client_addresses` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to the model.

Issue 2: **Foreign key in `applications.client_id` missing `ondelete` parameter**  
> Fix: Update ForeignKey definition to include `ondelete="CASCADE"` or appropriate behavior, e.g., `ForeignKey("clients.id", ondelete="CASCADE")`.

Issue 3: **Missing index on `clients.email` column**  
> Fix: Add `Index('ix_clients_email', 'email')` to ensure performant lookups by email.

Issue 4: **Detected lazy-loaded relationship in `Client.applications` without eager loading in service**  
> Fix: Annotate relationship with `lazy="selectin"` or ensure services use `selectinload()` when querying clients with applications.

Issue 5: **Financial field `application.loan_amount` uses Float instead of Decimal**  
> Fix: Change column type to `Numeric(19, 4)` to comply with precision requirements for monetary values.

---

📚 LEARNINGS (compressed):  
1. [high] Always define `updated_at` with `onupdate=func.now()` for audit integrity  
2. [high] Specify `ondelete` behavior for all ForeignKey definitions  
3. [high] Index all frequently queried fields like email and FKs  
4. [high] Prevent N+1 queries via `selectinload()` or `joinedload()` in service layers  
5. [high] Never use Float for financial data — always use `Decimal` or `Numeric`