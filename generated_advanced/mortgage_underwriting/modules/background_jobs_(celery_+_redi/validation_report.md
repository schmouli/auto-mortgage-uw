```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/jobs/models.py, line 14
  Issue: Financial precision — Missing Decimal usage for potential monetary fields (schedule, description). While these aren't explicitly monetary, regulatory requires ALL financial values use Decimal. Either clarify non-financial or convert.
  Fix: Clarify if any field could hold financial data; otherwise exempt with comment "# non-financial"

- File: mortgage_underwriting/modules/jobs/services.py, line 49
  Issue: Type hint missing for `payload` parameter in `trigger_job()` method when calling without payload
  Fix: Add Optional[] annotation to match schema

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/jobs/routes.py, line 37
  Issue: Bare except clause catches generic Exception but does not log or re-raise properly
  Fix: Replace with specific exception handling and include exc_info=True in logging

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/jobs/services.py, line 50
  Issue: Using datetime.utcnow() directly instead of timezone-aware UTC (violates audit requirements)
  Fix: Use datetime.now(timezone.utc) for all timestamps

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/jobs/exceptions.py, lines 1-15
  Issue: Unused custom exceptions defined but not used in service layer
  Fix: Either remove unused exceptions or implement them in services.py

BLOCKED: Regulatory Compliance
- File: mortgage_underwriting/modules/jobs/models.py
  Issue: Missing 5-year retention policy enforcement on JobExecutionLog (FINTRAC requirement)
  Fix: Add indexed created_at field and document retention strategy

Additional Issues:
- File: mortgage_underwriting/modules/jobs/routes.py, line 23
  Issue: Pagination missing from list endpoints as per learning #4
  Fix: Add skip/limit query parameters with maximum limit of 100
```