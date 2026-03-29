```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/auth/models.py, line 25
  Issue: `phone: Mapped[Optional[str]]` lacks explicit Optional[T] annotation
  Fix: Annotate as `Mapped[Optional[str] | None]` or `Mapped[str | None]`

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/auth/services.py, line 33
  Issue: Custom exception raised directly instead of using module-specific exceptions from exceptions.py
  Fix: Replace with `raise WeakPassword()` from exceptions.py

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/auth/services.py, line 109
  Issue: Logs user ID after DB commit; should log attempt before sensitive operation
  Fix: Add `logger.info("updating_current_user", user_id=user_id)` prior to query

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/auth/models.py
  Issue: Missing docstrings for class User and class RefreshToken
  Fix: Add Google-style docstrings explaining purpose and field meanings

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/auth/services.py, line 125
  Issue: Function `get_current_user` missing docstring
  Fix: Add docstring describing retrieval of active user by ID

BLOCKED: Regulatory Compliance (PIPEDA) failed
- File: mortgage_underwriting/modules/auth/models.py
  Issue: Phone number stored without encryption consideration
  Fix: Document whether phone qualifies as PII requiring encryption under PIPEDA

BLOCKED: Regulatory Compliance (FINTRAC) failed
- File: mortgage_underwriting/modules/auth/__init__.py
  Issue: Module missing audit trail policy for user lifecycle events
  Fix: Implement immutable audit logs for user registration, activation, deactivation
```