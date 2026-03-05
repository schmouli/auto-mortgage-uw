⚠️ BLOCKED

1. **[CRITICAL] integration_tests.py ~L28-29**: Raw SQL string `f"SELECT * FROM documents WHERE id = '{data['id']}'"` violates "No raw SQL strings" rule. Use SQLAlchemy ORM with `select(Document).where(Document.id == data['id'])` instead. This also introduces SQL injection risk even in test context.

2. **[CRITICAL] integration_tests.py ~L32**: Incorrect test logic uses placeholder `uuid4()` instead of actual document ID from response. Should reference `data['id']` from the API response to verify DB persistence correctly.

3. **[HIGH] unit_tests.py ~L58**: Generic `ValueError` raised for unsupported file type instead of domain-specific exception from `exceptions.py`. Should raise `DocumentValidationError` or similar module-specific exception with structured error response.

4. **[HIGH] integration_tests.py ~L95**: Magic number `50 * 1024 * 1024` (50MB) hardcoded for file size limit test. Should reference a configurable constant (e.g., `MAX_FILE_SIZE_BYTES` from `common/config.py`) to ensure test aligns with actual service limits.

5. **[HIGH] conftest.py ~L45**: Magic number `1024000` (1MB) in `sample_document_payload` fixture. Extract to named constant `TEST_FILE_SIZE_BYTES` for maintainability and to avoid duplication across tests.

... and 4 additional warnings (lower severity):
- Missing verification of structured error responses (`{"detail": "...", "error_code": "..."}`)
- No tests verifying PIPEDA compliance (PII encryption in documents)
- `app` fixture doesn't override storage/virus scanner dependencies completely
- Test methods lack docstrings documenting purpose and compliance verification scope