```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/clients/models.py, line 7
  Issue: Missing type hint for `id` field using `Mapped[int]` without specifying SQLAlchemy column type in model definition
  Fix: Specify both the Mapped type and Column type explicitly for clarity and consistency

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/clients/services.py, line 20
  Issue: Logger call uses `logger.info("creating_client", email=payload.email)` which may expose PII (email) in logs
  Fix: Remove PII from log statements per PIPEDA compliance; use client_id or masked values only

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/clients/services.py, line 20
  Issue: Missing docstrings for public methods in ClientService class
  Fix: Add docstrings to all public methods explaining purpose, arguments, returns, and exceptions raised
```