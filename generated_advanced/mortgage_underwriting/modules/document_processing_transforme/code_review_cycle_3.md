⚠️ BLOCKED

1. **[CRITICAL] services.py ~L41**: `submit_extraction()` returns random `uuid.uuid4()` as `job_id` instead of database `extraction.id` (int). The `get_extraction_status()` and `get_extraction_result()` methods query `Extraction.id == job_id` with a UUID parameter, causing permanent 404s. **Fix**: Return `job_id=extraction.id` and change schema/route to use `int` type instead of `UUID`.

2. **[CRITICAL] models.py ~L19**: `extracted_json` column stores PII (SIN, DOB, income) in plain JSON violating PIPEDA encryption-at-rest requirement. **Fix**: Encrypt the JSON blob using `common.security.encrypt_pii()` before storage and decrypt on retrieval in the service layer.

3. **[HIGH] services.py ~L15**: `application` relationship is defined but not eagerly loaded with `selectinload()`. Potential N+1 query risk if future code accesses `extraction.application`. **Fix**: Add `.options(selectinload(Extraction.application))` to both SQLAlchemy queries.

4. **[HIGH] exceptions.py**: `JobNotFoundError`, `InvalidDocumentTypeError`, and `ExtractionProcessingError` are defined but never raised. `services.py` imports `JobNotFoundError` but returns `None` instead. **Fix**: Raise `JobNotFoundError` in service layer and catch it in routes; add document type validation and raise `InvalidDocumentTypeError`; raise `ExtractionProcessingError` on processing failures.

5. **[MEDIUM] routes.py ~L25**: `/extract` endpoint accepts `file: UploadFile` parameter that is never used or validated. If provided, it should be uploaded to S3 and generate the `s3_key`. **Fix**: Either remove the parameter or implement file handling logic with proper validation.

... and 2 additional warnings (lower severity, address after critical issues are resolved)