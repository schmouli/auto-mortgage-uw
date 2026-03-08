BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/underwriting/services.py, line 134
  Issue: Variable `cmhc_required` referenced as `cmh` in return statement
  Fix: Change `cmh` to `cmhc_required`

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/underwriting/routes.py, line 13
  Issue: Import statement incomplete due to truncation
  Fix: Complete the import statement for schemas

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/underwriting/services.py, line 1 onwards
  Issue: Missing docstrings for class `UnderwritingService` and several methods
  Fix: Add docstrings for all public classes and methods explaining purpose, arguments, returns, and exceptions

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/underwriting/models.py, line 103
  Issue: Back-populated relationship defined outside model class
  Fix: Move relationship definition inside `UnderwritingResult` class or ensure it's correctly linked in dependent models

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/underwriting/services.py, line 17
  Issue: Potential PII leakage in log message
  Fix: Remove `property_value` from log context or ensure it's sanitized

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/underwriting/routes.py, line 10
  Issue: Incomplete import statement
  Fix: Complete the import of schemas from mortgage_underwriting.modules.underwriting.schemas