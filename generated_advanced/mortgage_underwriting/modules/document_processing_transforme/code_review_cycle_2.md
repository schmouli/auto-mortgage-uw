⚠️ BLOCKED

1. **[CRITICAL]** services.py ~L40: `job_id` is a random UUID not stored in database - `Extraction` model uses integer `id` primary key, but API returns UUID that cannot match any record. Queries in `get_extraction_status` and `get_extraction_result` compare UUID against integer column, causing type errors and logical failures. **Fix**: Add `job_id: Mapped[UUID]` column to `Extraction` model and store the generated UUID, or change API to use integer `id`.

2. **[CRITICAL]** routes.py ~L23: `application_id` type mismatch - Form parameter converted with `UUID(application_id)` but `DPTExtractionRequest` schema expects `int`. This causes Pydantic validation errors. **Fix**: Change to `int(application_id)` to match schema's integer field type.

3. **[CRITICAL]** services.py ~L35: `model_version` not provided when creating `Extraction` record - column is `nullable=False` but omitted from constructor, causing database constraint violation. **Fix**: Add `model_version=default_model_version` to `Extraction()` constructor.

4. **[HIGH]** services.py ~L15: `default_confidence_threshold = 0.85` uses float - should be `Decimal("0.85")` for decimal precision consistency with `Numeric` columns. **Fix**: Use `Decimal("0.85")` from the `decimal` module.

5. **[HIGH]** services.py ~L55: Service returns `None` instead of raising `JobNotFoundError` - violates pattern where service layer raises domain exceptions. **Fix**: Raise `JobNotFoundError()` instead of returning `None`, and have routes catch it.

... and 5 additional warnings (lower severity, address after critical issues are resolved)