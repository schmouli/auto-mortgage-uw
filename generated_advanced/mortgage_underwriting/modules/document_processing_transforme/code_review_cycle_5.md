⚠️ BLOCKED

1. **[CRITICAL] services.py ~L48, L60**: UUID/ID mismatch breaks API contract — `submit_extraction()` generates random `uuid.uuid4()` for `job_id` but `get_extraction_status()` and `get_extraction_result()` query database using `Extraction.id` (Integer). The returned UUID can never match any database record. **Fix**: Add `job_id: Mapped[UUID] = mapped_column(UUID, unique=True, default=uuid.uuid4)` to `Extraction` model and query by `job_id` instead of `id`.

2. **[CRITICAL REGRESSION] models.py ~L14**: Primary key type mismatch — `id` is `Integer` but API contract expects `UUID` for job identifiers. **Fix**: Change `id` to `Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)` or add separate `job_id` UUID column while keeping integer PK.

3. **[HIGH] services.py ~L45, L58**: `JobNotFoundError` exception defined but never raised — services return `None` instead of raising domain exception. **Fix**: Replace `return None` with `raise JobNotFoundError(f"Extraction job {job_id} not found")` in both `get_extraction_status()` and `get_extraction_result()`.

4. **[MEDIUM] services.py ~L15-17**: Magic numbers without named constants — `default_processing_time = 45` and `default_confidence_threshold = 0.85` should be module-level constants. **Fix**: Define as `PROCESSING_TIME_SECONDS = 45` and `CONFIDENCE_THRESHOLD = Decimal("0.85")` with uppercase naming.

5. **[MEDIUM] services.py ~L45-50, L58-63**: Duplicated query logic violates DRY principle — both methods execute identical `select(Extraction).where(...)` query. **Fix**: Extract private helper `_get_extraction_by_id(job_id: UUID) -> Optional[Extraction]` and reuse in both methods.

... and 2 additional warnings (lower severity, address after critical issues are resolved)