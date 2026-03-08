```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/intake/models.py, line 25
  Issue: Field `date_of_birth` uses `str` type but stores encrypted data; should be `bytes` or clearly marked as encrypted string
  Fix: Use `bytes` for encrypted fields or add comment indicating encryption

- File: mortgage_underwriting/modules/intake/services.py, line 104
  Issue: Method `_calculate_ltv_and_insurance` not defined in provided code
  Fix: Include method implementation or remove call

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/intake/services.py, line 86
  Issue: Bare raise in `update_application` without context
  Fix: Catch specific exceptions and handle appropriately

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/intake/services.py, line 117
  Issue: Missing audit logging for sensitive operations (e.g., encryption, submission)
  Fix: Add structlog calls for key actions like encryption and submission

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/intake/services.py, line 104
  Issue: Missing docstring for private method `_calculate_ltv_and_insurance`
  Fix: Add docstring explaining purpose, args, and logic
```