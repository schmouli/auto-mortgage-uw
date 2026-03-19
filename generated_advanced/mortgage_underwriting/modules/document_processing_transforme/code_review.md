⚠️ BLOCKED

1. **[CRITICAL] models.py ~L41**: `extracted_json` mapped to `Text` type instead of `JSONB` — use `sqlalchemy.dialects.postgresql.JSONB` for PostgreSQL JSON storage to maintain queryability and type safety
2. **[CRITICAL] models.py**: Missing `created_by` audit field — FINTRAC requires immutable audit trail with user identification on all transaction records
3. **[CRITICAL] services.py ~L59**: Converting `Decimal` confidence to `float` for logging — violates "never use float for numeric values" principle; keep as `Decimal` or cast to `str`
4. **[CRITICAL] routes.py**: Incorrect error response structure — `detail={"detail": "...", "error_code": "..."}` creates nested `detail` keys; should be `detail="...", error_code="..."` with custom exception handler
5. **[CRITICAL] services.py**: No validation of `application_id` existence — route docstring promises HTTP 404 for missing applications, but service lets foreign key constraint fail at DB level; add explicit check and raise `NotFoundError`

... and 8 additional warnings (lower severity, address after critical issues are resolved)

**Key Architectural Issues:**
- **Enum duplication**: `DocumentTypeEnum` and `ExtractionStatusEnum` defined in both `models.py` and `schemas.py` — import from models to ensure single source of truth
- **Dead code**: `exceptions.py` defines custom exceptions that are never used; service uses generic `ValueError` and `NotFoundError` instead
- **DRY violation**: Duplicate query logic in `get_job_status()` and `get_extraction_result()` — extract to `_get_extraction_or_raise()` helper
- **Transaction safety**: Service methods lack try/except blocks with `await self.db.rollback()` on failure
- **Test mismatch**: Provided test files reference non-existent models (`DocumentRecord`, `ExtractionResult`) — tests are completely out of sync with implementation