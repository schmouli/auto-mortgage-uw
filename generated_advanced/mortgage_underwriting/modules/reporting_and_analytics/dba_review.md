⚠️ BLOCKED  
Issue 1: **Missing updated_at field on `report_configurations` table**  
> Fix: Add `updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())`  

Issue 2: **Email column in `analytics_subscriptions` missing index**  
> Fix: Add `Index('ix_analytics_subscriptions_email', 'email')`  

Issue 3: **Foreign key `user_id` in `report_exports` missing `ondelete` parameter**  
> Fix: Update to `ForeignKey("users.id", ondelete="CASCADE")`  

Issue 4: **Float used for `average_processing_time` in `performance_metrics`**  
> Fix: Change column type to `Numeric(19, 4)`  

Issue 5: **No pagination enforced in `get_report_list` service method**  
> Fix: Add `skip: int`, `limit: int` params (max 100), apply `.offset().limit()` in query  

📚 LEARNINGS (compressed):  
1. [high] Always pair `created_at` with `updated_at` including `onupdate=func.now()`  
2. [high] Index all FKs and filterable fields like email  
3. [high] Never use float for durations or metrics — use `Decimal(19,4)`  
4. [high] Enforce max limit (e.g., 100) on paginated endpoints  
5. [high] Always specify `ondelete` behavior for referential integrity