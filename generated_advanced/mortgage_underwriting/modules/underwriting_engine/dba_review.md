⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `underwriting_decision` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to model.

Issue 2: **Float used for `loan_amount` and `property_value` in `UnderwritingScenario`**  
> Fix: Replace `Float` with `Numeric(19, 4)` for all financial fields to ensure precision.

Issue 3: **Foreign key `client_id` in `underwriting_scenario` lacks `ondelete` parameter**  
> Fix: Specify `ondelete="CASCADE"` or appropriate behavior: `ForeignKey("client.id", ondelete="CASCADE")`

Issue 4: **Missing composite index on `scenario_id` + `decision_status` for filtering decisions by scenario and status**  
> Fix: Add `Index('ix_scenario_status', 'scenario_id', 'decision_status')` to support performant queries.

Issue 5: **No eager loading documented in service layer for `UnderwritingDecision.scenario` relationship**  
> Fix: In services, load relationships using `selectinload(UnderwritingDecision.scenario)` to prevent N+1 queries.

---

📚 LEARNINGS (compressed):  
1. [high] Always use `Decimal(19,4)` for financial data — never `float`  
2. [high] Every table must have `updated_at` with `onupdate=func.now()`  
3. [high] All foreign keys require `ondelete` clause (`CASCADE`, `SET NULL`, or `RESTRICT`)  
4. [high] Composite indexes improve multi-column query performance  
5. [high] Use `selectinload()` or `joinedload()` in services to avoid N+1 query bugs  

Please address the above issues before re-validation.