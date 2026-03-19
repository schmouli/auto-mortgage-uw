```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/dpt_service/services.py, line 73
  Issue: Argument `confidence: Decimal` is logged as `float(confidence)` which violates PII/logging rules
  Fix: Remove or redact financial values from logs; do not cast Decimal to float in logs

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/dpt_service/services.py, line 73
  Issue: Financial value (confidence) exposed in log message
  Fix: Exclude sensitive/financial data from logs per PIPEDA & OSFI B-20 requirements

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/dpt_service/models.py
  Issue: Missing updated_at field on Extraction model
  Fix: Add `updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())` to align with audit requirements

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/dpt_service/models.py
  Issue: No created_at / updated_at fields for tracking changes per FINTRAC
  Fix: Ensure all models have immutable audit trail fields per regulatory requirement

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/dpt_service/routes.py, lines 38, 55, 70
  Issue: Bare `except Exception:` used without filtering or handling specific exceptions
  Fix: Replace generic except blocks with explicit exception catching and appropriate HTTP responses
```