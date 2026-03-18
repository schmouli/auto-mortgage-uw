BLOCKED

Remaining issues:

1. **Missing Application model reference** - The `Extraction` model references `"Application"` in relationship but `Application` model not shown (line 39). Without confirming Application model has `back_populates="extractions"`, this creates a broken bidirectional relationship.

2. **No audit trail for PII handling** - Although no direct SIN/DOB fields exist in this model, per FINTRAC requirements any system processing financial documents must log identity verification events. Missing audit fields or triggers for immutable logging.

3. **Incomplete index coverage** - While basic indexes exist, there's no composite index on `(application_id, status)` which would optimize common filtering queries for application-level job status checks.

4. **Missing NOT NULL constraints** - Several fields like `document_type`, `s3_key` should have explicit nullability validation in DB (they do in Pydantic, but need enforcement at model level).

Fix before re-validation:
- Confirm Application model exists with correct back_populates
- Add composite index: `Index('ix_extractions_app_status', 'application_id', 'status')`
- Ensure all mandatory audit fields are present and logged appropriately
- Explicitly set nullable=False where applicable in model definitions

WARNING: Context may be incomplete regarding Application model definition and broader compliance integrations.