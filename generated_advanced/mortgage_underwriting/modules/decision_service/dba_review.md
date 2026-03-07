⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `decision_rules` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)` to the model.

Issue 2: **Float used for `max_ltv` and `min_credit_score` in `eligibility_criteria`**  
> Fix: Replace `Float` with `Numeric(5, 2)` for precise decimal storage.

Issue 3: **Missing composite index on `eligibility_criteria.is_active` + `eligibility_criteria.product_type`**  
> Fix: Add `Index('ix_eligibility_criteria_active_product', 'is_active', 'product_type')` for efficient filtering.

Issue 4: **Foreign key `DecisionRuleSet.rule_set_id` missing `ondelete` parameter**  
> Fix: Update to `ForeignKey("rule_sets.id", ondelete="CASCADE")` to enforce referential integrity.

Issue 5: **Lazy-loaded relationship detected in `DecisionRuleSet.rules` without eager loading strategy documented**  
> Fix: Annotate relationship with `selectinload()` or `joinedload()` in service query; update service docstrings accordingly.

📚 LEARNINGS (compressed):  
1. [high] Always use `Decimal(19,4)` for financial/ratio values — prevents rounding errors  
2. [high] All models require `created_at`, `updated_at` with timezone-aware `DateTime`  
3. [med] Composite indexes prevent full-table scans on business-critical filters  
4. [med] Specify `ondelete` behavior for all foreign keys to maintain consistency  
5. [low] Type-hint all relationships using `Mapped[...]` syntax for SQLAlchemy 2.0+ compliance