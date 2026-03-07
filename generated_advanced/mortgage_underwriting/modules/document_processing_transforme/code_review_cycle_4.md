⚠️ BLOCKED

1. **[CRITICAL] services.py ~L38: Missing required model_version field** - Extraction.model_version is defined as nullable=False but not provided in the constructor call. Add `model_version=default_model_version` when creating the Extraction record.

2. **[CRITICAL] services.py ~L44, ~L50, ~L70: UUID/Integer ID type mismatch** - The API exposes job_id as UUID, but Extraction.id is an Integer primary key. The service generates random UUIDs that never map to database records, making status/result queries impossible. Add a dedicated UUID column (`job_id: Mapped[UUID]`) to the Extraction model and index it for lookups.

3. **[CRITICAL] services.py / routes.py: Domain exceptions not utilized** - `JobNotFoundError` is defined but never raised. The service returns `None`, forcing routes to manually construct HTTPException responses. Implement proper exception flow: raise `JobNotFoundError` in service methods and catch it in routes to return structured errors.

4. **[HIGH] models.py ~L20: PIPEDA compliance violation** - The `extracted_json` field stores document data without encryption. If this JSON contains PII (SIN, DOB, income), it must be encrypted at rest using `encrypt_pii()` from `common.security` before persistence.

5. **[HIGH] models.py: FINTRAC audit trail incomplete** - Missing `created_by` field required for immutable audit trail compliance. Add `created_by: Mapped[str] = mapped_column(String(100), nullable=False)` to track the authenticated user who initiated the extraction.

... and 2 additional warnings (lower severity, address after critical issues are resolved)