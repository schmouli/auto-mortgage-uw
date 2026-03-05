⚠️ BLOCKED  
Issue 1: **Missing composite index** on `transaction` table for common query pattern (`client_id`, `created_at`) — add `Index('ix_transaction_client_created', 'client_id', 'created_at')`  
Issue 2: **Float used for monetary field** in `transaction.amount` — change to `Numeric(19, 4)`  
Issue 3: **N+1 query risk** in `services.get_transactions_for_client()` — missing `selectinload(Transaction.audit_logs)`  
Issue 4: **No pagination** in `list_transactions` service method — implement `skip`/`limit` with max 100  

---

### 📚 Required Fixes Summary

1. **Composite Index**: Add multi-column index for frequent combined filters.
2. **Monetary Precision**: Replace `Float` with `Decimal(19, 4)` for all financial fields.
3. **Eager Loading**: Prevent N+1 by using `selectinload()` or `joinedload()`.
4. **Pagination Enforcement**: Limit list endpoints to max 100 records per page.

Apply these changes across `models.py`, `services.py`, and ensure migrations reflect safe schema evolution.