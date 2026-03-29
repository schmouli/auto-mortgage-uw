```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/dpt/models.py, line 58
  Issue: `confidence` field uses `Numeric(5, 4)` which may cause precision issues for financial confidence scoring
  Fix: Use `Numeric(6, 5)` or higher precision for confidence scores to align with Decimal best practices

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/dpt/services.py, line 89
  Issue: Bare except clause catches all exceptions without logging context
  Fix: Replace `except Exception:` with specific exception handling and proper logging using `logger.error("failed", exc_info=True)`

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/dpt/routes.py, line 34
  Issue: Dependency injection annotation incorrectly references `get_async_session` as a type instead of callable
  Fix: Correct dependency signature to properly inject the database session

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/dpt/models.py, line 28
  Issue: Missing docstring for `ExtractionJob` class
  Fix: Add comprehensive docstring describing purpose, constraints, and usage
```