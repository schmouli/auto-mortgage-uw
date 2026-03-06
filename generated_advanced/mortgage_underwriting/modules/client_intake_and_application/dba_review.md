⚠️ BLOCKED  
Issue 1: **Missing `updated_at` field** on the `Application` model.  
> 🔧 Fix: Add `updated_at = Column(DateTime(timezone=True), onupdate=func.now())` to match timestamp integrity rules.

Issue 2: **Email column missing index** in `Client` model.  
> 🔧 Fix: Add `Index('ix_client_email', 'email')` for efficient lookups.

Issue 3: **Foreign key in `Application.client_id` missing `ondelete` parameter**.  
> 🔧 Fix: Update ForeignKey to: `ForeignKey("clients.id", ondelete="CASCADE")`.

Issue 4: **Relationship definitions missing `Mapped` type hints and `back_populates`**.  
> 🔧 Fix: Use `client: Mapped["Client"] = relationship("Client", back_populates="applications")` in `Application`, and vice versa in `Client`.

Issue 5: **No pagination implemented in list queries in services**.  
> 🔧 Fix: Add `(skip: int = 0, limit: int = 100)` params to service methods and apply `.offset().limit()` in SQL queries.

Issue 6: **Float used for `loan_amount` and `property_value` in `Application`**.  
> 🔧 Fix: Replace `Float` with `Numeric(19, 4)` for all financial fields to ensure precision.

---

📚 LEARNINGS (compressed):  
1. [high] Always include `updated_at` with `onupdate=func.now()`  
2. [high] Index all lookup fields like email  
3. [high] All FKs need `ondelete=` specified  
4. [high] Use `Mapped[T]` + `back_populates` for SQLAlchemy 2.0  
5. [high] Never use `float` for money – use `Decimal(19,4)`  
6. [high] Always paginate list endpoints (`skip`, `limit`)  

✅ Once fixed, revalidate with full checklist.