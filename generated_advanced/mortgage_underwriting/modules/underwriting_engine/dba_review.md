⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `underwriting_decision` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to model  

Issue 2: **Float used for `loan_amount` and `property_value` in `UnderwritingApplication`**  
> Fix: Replace `Float` with `Numeric(19, 4)` for all financial fields  

Issue 3: **Foreign key `application_id` in `UnderwritingDecision` lacks `ondelete` parameter**  
> Fix: Update ForeignKey definition to include `ondelete="CASCADE"` or appropriate behavior  

Issue 4: **Missing composite index on (`applicant_email`, `status`) in `UnderwritingApplication`**  
> Fix: Add `Index('ix_applicant_status', 'applicant_email', 'status')`  

Issue 5: **Lazy-loaded relationship `application.decisions` may cause N+1 queries**  
> Fix: Eager load using `selectinload()` or `joinedload()` in service query  

Issue 6: **No pagination implemented in `list_underwriting_applications` service method**  
> Fix: Add `skip` and `limit` parameters (max 100), apply in SQL query with `.offset().limit()`  

---

📚 LEARNINGS (compressed):  
1. [high] Always use `Decimal` for financial data – never `float`  
2. [high] Protect PII: encrypt SIN/DOB, never log them  
3. [high] Add `updated_at` with `onupdate=func.now()` to all tables  
4. [high] Use composite indexes for frequent multi-column queries  
5. [high] Prevent N+1: document and enforce eager loading in services  
6. [high] Paginate all list endpoints – unbounded queries cause memory issues