```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/portal/models.py, line 13
  Issue: Missing `updated_at` field in `ClientPortalActivity` model
  Fix: Add `updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)`

- File: mortgage_underwriting/modules/portal/models.py, line 53
  Issue: Missing `updated_at` field in `Notification` model (present but missing from `ClientPortalActivity`)
  Fix: Already compliant

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/portal/routes.py, line 34
  Issue: Generic exception handler hides specific errors and doesn't map to structured responses
  Fix: Replace generic `except Exception as e` with specific exception handlers that return {"detail": "...", "error_code": "..."}

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/portal/services.py, line 25
  Issue: Using raw `func` instead of `sql_func` alias defined in imports
  Fix: Change `func.count()` to `sql_func.count()` for consistency

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/portal/models.py, line 10
  Issue: Docstring mentions immutability but model allows updates (no audit trail enforcement)
  Fix: Either remove immutability claim or implement immutable pattern (e.g., soft-delete + insert-only logic)

APPROVED: Gate 2, Gate 5 passed
```