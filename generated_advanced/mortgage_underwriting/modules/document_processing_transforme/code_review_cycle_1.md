⚠️ BLOCKED

1. **[CRITICAL]** services.py ~L58: Hardcoded query ID in `get_extraction_result` - `Extraction.id == 1` must use `job_id` parameter to locate the correct record
2. **[CRITICAL]** routes.py ~L27: Type mismatch - route converts `application_id` to `UUID()` but `DPTExtractionRequest` schema expects `int`, causing Pydantic validation error
3. **[CRITICAL]** services.py ~L35: Job ID not persisted - `job_id` (UUID) returned to client is never stored in `Extraction` model (which uses int PK), making retrieval by job_id impossible
4. **[HIGH]** exceptions.py: Exceptions defined but never used - `JobNotFoundError` is imported but service returns `None` instead of raising the exception
5. **[HIGH]** services.py ~L45: `get_extraction_status` returns mock response instead of querying database for actual job status

... and 2 additional warnings (lower severity, address after critical issues are resolved)