```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/policy/services.py, line 106
  Issue: Financial ratio stored as float in details dict
  Fix: Use Decimal for all financial values

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/policy/routes.py, line 34
  Issue: Undefined variable `logger` 
  Fix: Import structlog and initialize logger

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/policy/services.py, line 85
  Issue: PII-related data (credit_score) logged without protection
  Fix: Remove sensitive data from logs or hash before logging

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/policy/services.py, line 134
  Issue: Missing docstring for `_extract_lender_name` method
  Fix: Add proper docstring explaining parsing logic

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/policy/models.py, line 28
  Issue: Missing docstrings for model fields
  Fix: Add column-level documentation for clarity
```