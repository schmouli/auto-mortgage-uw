```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/underwriting/services.py, line 27
  Issue: Method `calculate_qualification` is declared as static but uses instance attribute `self.db` indirectly through `self`
  Fix: Remove @staticmethod decorator and ensure method signature includes `self`

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/underwriting/routes.py, line 39
  Issue: Bare except clause catches all exceptions without proper handling or logging
  Fix: Replace with specific exception types and log with context using structlog

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/underwriting/services.py, line 83
  Issue: Financial values logged as floats which may expose raw data
  Fix: Avoid including actual monetary amounts in logs; use ratio percentages only

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/underwriting/models.py, line 1
  Issue: Missing docstring for module
  Fix: Add one-line module description at top of file

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/underwriting/services.py, line 27
  Issue: Complex business logic lacks inline explanatory comments
  Fix: Annotate key steps such as stress test calculation, CMHC premium tiers, and decision logic with why-not-what commentary
```