```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/orchestrator/models.py, line 12
  Issue: Missing type hints for mapped columns (e.g., Mapped[Decimal], Mapped[bool], etc.)
  Fix: Add proper SQLAlchemy 2.0+ style type hints using Mapped[T]

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/orchestrator/services.py, line 14
  Issue: Bare except clause catches all exceptions without specificity
  Fix: Catch specific exceptions like IntegrityError or ValueError instead of generic Exception

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/orchestrator/services.py, line 15
  Issue: Logs raw exception string which may contain PII or sensitive data
  Fix: Log only safe identifiers and use exc_info=True for stack trace

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/orchestrator/services.py, line 9
  Issue: Missing docstring for MyService class
  Fix: Add class-level docstring explaining purpose and usage

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/orchestrator/services.py, line 11
  Issue: Missing docstring for create method
  Fix: Add method-level docstring including args, returns, and possible raises
```