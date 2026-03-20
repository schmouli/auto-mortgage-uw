```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/application/models.py, line 14
  Issue: date_of_birth is stored as plain text but should be encrypted per PIPEDA requirements
  Fix: Encrypt date_of_birth using AES-256 (similar to sin_encrypted)

- File: mortgage_underwriting/modules/application/models.py, line 78
  Issue: Missing updated_at field with onupdate=func.now() for MortgageApplication model
  Fix: Add updated_at column with proper configuration

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/application/services.py, line 115
  Issue: Bare except clause in _calculate_ratios_and_insurance method
  Fix: Specify exception types and handle appropriately

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/application/services.py, line 116
  Issue: Potential PII exposure in logs through client object logging
  Fix: Avoid logging entire objects that may contain PII; log only necessary identifiers

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/application/services.py, line 85
  Issue: Missing docstring for submit_application method
  Fix: Add docstring explaining function purpose, parameters, and return value
```