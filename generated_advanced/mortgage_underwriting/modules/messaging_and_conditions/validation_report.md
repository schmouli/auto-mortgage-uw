```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/mortgage/services.py, line 13
  Issue: Function `create` missing return type hint
  Fix: Add `-> MortgageApplication` (already present, but logger.info missing structured context)

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/mortgage/services.py, line 19
  Issue: Bare `except Exception as e` without specific exception handling
  Fix: Catch specific exceptions like `IntegrityError`, `DataError`, etc., and re-raise as HTTP-friendly errors

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/mortgage/routes.py, line 21
  Issue: Logger not imported — `logger.error` will raise NameError
  Fix: Import `structlog` and define `logger = structlog.get_logger()` at top of file

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/mortgage/routes.py, line 12
  Issue: Function `create_item` missing docstring describing purpose, args, returns, raises
  Fix: Add Google-style or Sphinx-style docstring

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/mortgage/services.py, line 10
  Issue: Class `MyService` method `create` missing detailed docstring
  Fix: Document parameter types, return value, possible exceptions raised

BLOCKED: Regulatory Compliance (FINTRAC/PIPEDA)
- Files: models.py, services.py, routes.py
  Issue: No audit trail fields (`created_by`, immutable storage), no SIN/DOB encryption check
  Fix: Add `created_by: Mapped[str]`, enforce encryption via `common.security.encrypt_pii()` where applicable

⚠️ WARNING: Context truncated — cannot fully validate tests.py or conftest.py
```