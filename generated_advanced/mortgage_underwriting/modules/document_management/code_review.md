⚠️ **BLOCKED**

1. **[CRITICAL]** `schemas.py` ~L35: `DocumentResponse` exposes internal `file_path` field in API responses - violates security principle and PIPEDA data minimization. **Fix**: Remove `file_path` from `DocumentResponse`; create separate internal schema if needed for service-layer use.

2. **[CRITICAL]** `schemas.py` ~L21: `DocumentCreate` includes `notes` field but `models.py` `Document` table has no corresponding column. **Fix**: Add `notes = mapped_column(Text, nullable=True)` to `Document` model or remove from schema.

3. **[CRITICAL]** `routes.py` ~L42-48: `upload_document` constructs raw `dict` payload instead of `DocumentCreate` Pydantic model - bypasses all validation, type safety, and Field constraints. **Fix**: Use `DocumentCreate.model_validate()` or instantiate properly typed object.

4. **[CRITICAL]** `services.py` ~L140: `delete_document()` uses `db.delete()` for permanent record removal - violates FINTRAC immutable audit trail and 5-year retention requirements. **Fix**: Implement soft delete pattern with `is_deleted` flag and filtered queries.

5. **[CRITICAL]** `services.py` ~L75-85: `upload_document` creates `Document` without required `uploaded_by` field - violates foreign key constraint and FINTRAC identity verification logging. **Fix**: Add `uploaded_by: int` parameter to method and `DocumentCreate` schema, propagate from authenticated user.

... and 11 additional warnings (including error response format violations, missing pagination, weak filename sanitization, N+1 query potential, undefined exceptions, and test import mismatches) - address after critical issues are resolved.