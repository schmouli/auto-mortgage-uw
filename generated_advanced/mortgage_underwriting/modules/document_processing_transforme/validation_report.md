```
BLOCKED: Gate 1 failed
- File: mortgage_underwriting/modules/dpt/models.py, line 27
  Issue: `id` field uses `default=func.gen_random_uuid()` which may cause issues with async SQLAlchemy sessions; prefer application-level UUID generation
  Fix: Generate UUID in service/route layer using `uuid.uuid4()`

BLOCKED: Gate 3 failed
- File: mortgage_underwriting/modules/dpt/routes.py, line 79
  Issue: Bare `except Exception as e:` catches all exceptions without specificity
  Fix: Catch specific exceptions like `AppException`, re-raise or handle accordingly

BLOCKED: Gate 4 failed
- File: mortgage_underwriting/modules/dpt/routes.py, line 34
  Issue: No structured logging of incoming requests or key operations
  Fix: Add `logger.info("dpt_submit_extraction_request", application_id=str(application_id))` at start of route

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/dpt/routes.py, lines 16-17
  Issue: Constants `MAX_FILE_SIZE` not in UPPER_CASE per naming convention
  Fix: Rename to `MAX_FILE_SIZE_BYTES` and define in `common/config.py` instead of hardcoded

BLOCKED: Gate 6 failed
- File: mortgage_underwriting/modules/dpt/services.py, line 49
  Issue: Missing inline comment explaining why `selectin` loading is used for relationship
  Fix: Add comment "# Eager load related Application for audit completeness"

⚠️ REGULATORY WARNING (Not blocking but requires attention):
- FINTRAC compliance: No audit trail implemented for document submission timestamps or user identity
- PIPEDA concern: No encryption-at-rest declared for stored documents or metadata
```