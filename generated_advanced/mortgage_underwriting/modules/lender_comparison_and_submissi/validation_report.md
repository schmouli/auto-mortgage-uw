```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/lender/services.py, line 105
  Issue: Return type hint missing for method `update_submission_status`
  Fix: Add return type annotation `-> LenderSubmission`

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/lender/services.py, line 76
  Issue: PII potentially logged in `logger.info("matching_lenders", ...)`
  Fix: Remove sensitive fields like `client_id`, `gross_monthly_income`, etc. from log

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/lender/services.py, line 68
  Issue: No docstring for complex logic in `match_lenders`
  Fix: Add docstring explaining GDS/TDS/stress test logic per OSFI B-20

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/lender/services.py, line 105
  Issue: Bare `except Exception as e:` without specific handling
  Fix: Catch more specific exceptions or re-raise with context

BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/lender/tests/conftest.py, line 43
  Issue: Schema mismatch between test data and actual model (`Submission` vs `LenderSubmission`)
  Fix: Align fixture names and imports with real models

BLOCKED: Gate 2 failed
- File: mortgage_underwriting/modules/lender/routes.py, line 53
  Issue: Inconsistent naming — route path uses `/applications/{application_id}` but service assumes embedded ID
  Fix: Either extract `application_id` from path consistently or decouple it from payload
```