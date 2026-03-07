⚠️ BLOCKED  
Issue 1: **Missing `updated_at` field** on the `Workflow` model  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 Fix: Add `updated_at = Column(DateTime(timezone=True), onupdate=func.now())`  

Issue 2: **Foreign key `client_id` missing `ondelete` parameter** in `Workflow` model  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 Fix: Update to `ForeignKey("clients.id", ondelete="CASCADE")`  

Issue 3: **Missing index on `client_id` foreign key**  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 Fix: Add `Index('ix_workflow_client_id', 'client_id')`  

Issue 4: **No composite index for common query pattern** `(status, client_id)`  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 Fix: Add `Index('ix_workflow_status_client', 'status', 'client_id')`  

Issue 5: **Float used for `loan_amount` and `property_value`**  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 Fix: Replace `Float` with `Numeric(19, 4)`  

Issue 6: **No pagination enforced in service layer** for listing workflows  
&nbsp;&nbsp;&nbsp;&nbsp;🔧 Fix: Add `skip: int`, `limit: int` params to service method, enforce `min(limit, 100)`  

📚 LEARNINGS (compressed):  
1. [high] Always add `updated_at` with `onupdate=func.now()`  
2. [high] FKs must specify `ondelete` behavior  
3. [high] Index all FKs and common query combos (`Index(...)`)  
4. [high] Never use `Float` for money – use `Decimal(19, 4)`  
5. [high] Enforce pagination (`skip`, `limit`) on all list endpoints