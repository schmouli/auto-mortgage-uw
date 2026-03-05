⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `underwriting_rules` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to model.

Issue 2: **Float used for `loan_amount` and `property_value` in `UnderwritingApplication`**  
> Fix: Replace `Float` with `Numeric(19, 4)` for all financial fields to ensure precision.

Issue 3: **Missing composite index on `application_id` and `status` in `UnderwritingDecision`**  
> Fix: Add `Index('ix_application_status', 'application_id', 'status')` for efficient filtering.

Issue 4: **Foreign key `client_id` in `UnderwritingApplication` missing `ondelete` parameter**  
> Fix: Update ForeignKey to include `ondelete="CASCADE"` or appropriate referential action.

Issue 5: **Lazy-loading relationship detected in `UnderwritingApplication.client` without eager loading in service**  
> Fix: Annotate relationship with `Mapped["Client"]` and use `selectinload()` or `joinedload()` in query execution.

Issue 6: **No pagination implemented in `list_underwriting_applications()` service method**  
> Fix: Add `skip: int`, `limit: int` parameters (max 100) and apply `.offset().limit()` in query.

📚 LEARNINGS (compressed):  
1. [high] Always use `Decimal(19,4)` for financial data — never `float`.  
2. [high] Every table must have `updated_at` with `server_default` and `onupdate`.  
3. [high] Apply composite indexes for multi-column query performance.  
4. [high] Use `Mapped[...]` syntax with `back_populates` for bidirectional relationships.  
5. [high] Prevent N+1 by specifying eager loading (`selectinload`) in services.  
6. [high] Enforce pagination on all list endpoints with `skip`/`limit`.