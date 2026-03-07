⚠️ BLOCKED

1. **[CRITICAL] schemas.py ~L71**: `ClientResponse` inherits from `ClientBase` which includes PII fields (`sin`, `date_of_birth`), violating PIPEDA by exposing encrypted SIN/DOB in API responses. **Fix**: Create separate `ClientPublicResponse` schema that excludes all sensitive fields, returning only `id`, `first_name`, `last_name`, `email`, `phone`, `addresses`, `created_at`, `updated_at`.

2. **[CRITICAL] services.py ~L32**: Logging PII data - `logger.info()` includes `first_name` and `last_name` parameters. This violates PIPEDA's logging prohibition. **Fix**: Remove PII from log statements; log only `client_id` after successful creation.

3. **[CRITICAL] models.py**: Missing FINTRAC audit trail compliance. All three models lack `created_by` and `updated_by` fields to track who created/modified records. **Fix**: Add `created_by: Mapped[str] = mapped_column(String(100), nullable=False)` and `updated_by: Mapped[str] = mapped_column(String(100), nullable=False)` to `Client`, `ClientAddress`, and `MortgageApplication`.

4. **[CRITICAL] models.py**: Missing CMHC insurance requirement fields. `MortgageApplication` model lacks `ltv_ratio`, `insurance_required`, and `insurance_premium` fields needed for LTV>80% insurance calculations and audit trail. **Fix**: Add `ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2))`, `insurance_required: Mapped[bool]`, and `insurance_premium: Mapped[Decimal] = mapped_column(Numeric(19, 4))`.

5. **[CRITICAL] services.py ~L78-86**: `update_client()` deletes and recreates address records, violating FINTRAC's immutable audit trail principle. **Fix**: Implement address updates using in-place modifications with proper versioning or add `is_active` flag instead of physical deletion.

... and 8 additional warnings (address DRY violations, missing type hints, incomplete test coverage) — address after critical compliance issues are resolved.