```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/mortgage/models.py, line 12
  Issue: `created_at` and `updated_at` fields do not use `Mapped[DateTime]` with proper type annotation including timezone awareness
  Fix: Use `Mapped[datetime]` and ensure `DateTime(timezone=True)` is correctly applied

BLOCKED: Gate 2 failed
- File: mortgage_underwriting/modules/mortgage/services.py, line 14
  Issue: Function `create` missing return type hint
  Fix: Add `-> MortgageApplication` return type

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/mortgage/routes.py, line 18
  Issue: Catches `ValueError` but does not handle other potential exceptions from service layer
  Fix: Catch more specific exceptions or propagate appropriately; consider using a global exception handler

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/mortgage/services.py, line 19
  Issue: Logs error message without including full traceback context
  Fix: Include `exc_info=True` in logger call to capture stack trace

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/mortgage/services.py, line 10
  Issue: Class `MyService` lacks docstring explaining its purpose
  Fix: Add module-level docstring describing business logic encapsulated by this service
```