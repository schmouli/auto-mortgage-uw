⚠️ BLOCKED  
Issue 1: **Missing updated_at field on table `users`**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to the model.

Issue 2: **Float used for `annual_income` column in `borrower` table**  
> Fix: Change column type to `Numeric(19, 4)` to ensure precision for financial data.

Issue 3: **Foreign key `client_id` in `loan_applications` missing `ondelete` parameter**  
> Fix: Specify `ondelete="CASCADE"` or appropriate referential action in ForeignKey definition.

Issue 4: **Missing composite index on `email` and `is_active` in `users` table**  
> Fix: Add `Index('ix_users_email_is_active', 'email', 'is_active')` for efficient filtering.

Issue 5: **Lazy-loaded relationship detected in `Client.applications` without documented eager loading in service**  
> Fix: Annotate relationship with `Mapped[list["LoanApplication"]] = relationship(back_populates="client", lazy="selectin")` and confirm service uses `selectinload()` or `joinedload()`.

Issue 6: **List endpoint in `loan_service` lacks pagination support**  
> Fix: Add `skip: int = 0, limit: int = 100` parameters to function signature and apply `.offset(skip).limit(limit)` in query.

📚 LEARNINGS (compressed):  
1. [high] Always include `updated_at` with `onupdate=func.now()` on all tables  
2. [high] Never use `float` for financial fields – use `Decimal(19, 4)`  
3. [high] Composite indexes prevent full-table scans on multi-field filters  
4. [high] Foreign keys must define `ondelete` to enforce referential integrity  
5. [high] Eager load relationships explicitly to avoid N+1 queries