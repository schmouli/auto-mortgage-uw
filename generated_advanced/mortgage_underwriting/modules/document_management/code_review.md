⚠️ BLOCKED

**Critical FINTRAC and PIPEDA violations detected. Module cannot proceed until resolved.**

1. **[CRITICAL] routes.py ~L115-125**: DELETE endpoint violates FINTRAC 5-year retention requirement. Documents must be soft-deleted (`is_deleted` flag) not permanently removed. **Fix**: Add `is_deleted: Mapped[bool]` to Document model, remove DELETE endpoint, replace with POST `/archive` that sets flag.

2. **[CRITICAL] services.py ~L140-150**: `delete_document()` permanently removes database records, breaking FINTRAC immutability rules. **Fix**: Implement soft delete pattern - update `is_deleted=True` and `deleted_at=datetime.now(timezone.utc)` instead of `self.db.delete()`.

3. **[CRITICAL] schemas.py ~L50**: `DocumentResponse.file_path` exposes filesystem paths containing PII, violating PIPEDA data minimization. **Fix**: Remove `file_path` from response schema; return signed download URL or stream file content directly.

4. **[CRITICAL] routes.py ~L42, ~L98**: Hardcoded user IDs (`uploaded_by = 1`, `verified_by = 1`) bypass authentication. **Fix**: Inject authenticated user via `Depends(get_current_user)` and pass `user.id` to service layer.

5. **[CRITICAL] services.py ~L85**: Virus scanning is placeholder logging only. **Fix**: Integrate ClamAV or similar scanner before `self.db.commit()`; reject infected files and log `file_hash` with scan result.

---

**[HIGH] Additional issues requiring immediate attention:**

6. **[HIGH] services.py ~L30**: Magic number `10 * 1024 * 1024` for file size limit. **Fix**: Define `MAX_FILE_SIZE_MB = 10` constant at module level.

7. **[HIGH] services.py ~L55, ~L105**: Uses `datetime.utcnow()` (deprecated in Python 3.12). **Fix**: Replace with `datetime.now(timezone.utc)`.

8. **[HIGH] services.py ~L65**: Hardcoded `allowed_mime_types` list. **Fix**: Move to `common/config.py` as `ALLOWED_DOCUMENT_MIME_TYPES`.

9. **[HIGH] services.py ~L170**: Hardcoded category mapping in `_get_document_category()`. **Fix**: Store mapping in database table `document_type_categories` for maintainability.

10. **[HIGH] routes.py ~L60**: `list_documents` missing pagination. **Fix**: Add `skip: int = 0, limit: int = 100` parameters to prevent unbounded result sets.

---

**... and 6 additional warnings (lower severity)**
- Missing indexes on `document_type`, `status`, `is_verified` columns
- No correlation_id in structlog calls
- No transaction context managers (`async with self.db.begin()`)
- Inconsistent error_code uniqueness (DOC_001 reused)
- DocumentUploadRequest schema defined but unused
- Test suite uses SQLite instead of PostgreSQL 15

**Regulatory Note**: All file paths must be encrypted at rest and access logged for FINTRAC audit trail. Current implementation logs `file_hash` but needs retention policy enforcement.