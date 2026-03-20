```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/fintrac/services.py, line 127
  Issue: Uses float() to convert Decimal in log — violates "NEVER use float for money" rule
  Fix: Log Decimal directly or convert to string: logger.info("...", amount=str(payload.amount))

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/fintrac/routes.py, line 36
  Issue: Bare except clause catches all exceptions without proper filtering
  Fix: Catch specific exceptions like AppException and NotFoundError separately

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/fintrac/models.py, line 29
  Issue: Model FintracVerification missing updated_at audit field (violates "ALWAYS include updated_at")
  Fix: Add updated_at column with DateTime(timezone=True), server_default=func.now(), onupdate=func.now()

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/fintrac/models.py, line 66
  Issue: Model FintracReport missing immutable audit trail requirement (record_created_at should be separate from updated_at)
  Fix: Rename created_at to record_created_at and keep updated_at as separate field

BLOCKED: Gate 5 failed
- File: mortgage_underwriting/modules/fintrac/exceptions.py, lines 1-15
  Issue: Custom exceptions do not inherit from common/exceptions.py AppException base class
  Fix: Inherit from AppException and ensure error_code propagation
```