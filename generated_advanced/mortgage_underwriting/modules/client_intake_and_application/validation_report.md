```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/client_intake/services.py, line 105
  Issue: Method `calculate_gds_tds` missing return type annotation
  Fix: Add `-> dict` return type hint

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/client_intake/services.py, line 117
  Issue: Bare `except Exception as e:` used in `calculate_gds_tds`
  Fix: Catch specific exceptions like `AppException`, or re-raise/log appropriately

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/client_intake/services.py, line 117
  Issue: Error logging lacks exception context (`exc_info=True`)
  Fix: Use `logger.error("Failed to calculate GDS/TDS", exc_info=True)` when catching exceptions

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/client_intake/services.py, line 105
  Issue: Missing docstring for public method `calculate_gds_tds`
  Fix: Add docstring explaining purpose, arguments, and return value per OSFI B-20 requirements

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/client_intake/models.py, line 23
  Issue: Field `date_of_birth_encrypted` should use `Mapped[str]` with `mapped_column` consistently (minor inconsistency)
  Fix: Not critical but ensure all fields follow consistent mapping style

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/client_intake/routes.py, line 67
  Issue: Docstrings missing for route handler functions
  Fix: Add docstrings describing endpoint behavior, parameters, and responses
```