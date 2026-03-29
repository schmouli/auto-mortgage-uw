**BLOCKED** – Critical security vulnerabilities identified. Remediate before merging.

---

### 🔴 CRITICAL FINDINGS

**CWE-306: Missing Authentication for Critical Function**
- **Affected:** `routes.py` – All endpoints (`@router.get/post`)
- **Pattern:** No `Depends(get_current_user)` or auth dependency
- **Fix:** Add authentication dependency to every endpoint. Implement JWT validation with `get_current_user()` from `common/security.py`.
- **Impact:** Unauthenticated attackers can access all reports, FINTRAC compliance data, and export sensitive mortgage analytics.

**CWE-639: Authorization Bypass Through User-Controlled Key**
- **Affected:** `routes.py:export_applications_report()`
- **Pattern:** `user_id: int = Query(...)` with no ownership validation
- **Fix:** Remove `user_id` from query params. Derive user context from authenticated token. Add role-check: `if not (user.is_admin or user.id == requested_user_id)`.
- **Impact:** IDOR allows any user to export reports for any other user, leaking PII and financial data.

---

### 🟠 HIGH SEVERITY

**FINTRAC Audit Trail Violation**
- **Affected:** `models.py` – `ReportCache`, `FintracReportSummary`, `ReportExportLog`
- **Pattern:** Missing `created_by`, `updated_at` fields; no immutable guarantees
- **Fix:** Add `created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))` and `updated_at` with `onupdate=func.now()`. Implement database-level `UPDATE` triggers or use `event.listens_for(Base, 'before_update')` to enforce immutability on compliance records.
- **Regulatory:** Violates FINTRAC 5-year retention and immutability requirements.

**Unvalidated Dynamic Input**
- **Affected:** `schemas.py:ReportExportRequest`
- **Pattern:** `filters: Optional[dict]` (raw dictionary)
- **Fix:** Replace with validated Pydantic model: `filters: Optional[ReportFilters]`. Add max depth and field name allow-list to prevent NoSQL injection in JSONB queries.
- **Impact:** Malicious filters could bypass data access controls or trigger expensive queries (DoS).

**Potential PII Leakage in Logs**
- **Affected:** `services.py:get_pipeline_summary()`
- **Pattern:** `logger.info("generating_pipeline_summary", filters=filters.dict())`
- **Fix:** Sanitize filters before logging. Implement `sanitize_for_logging()` that masks sensitive fields. Use `logger.info("event", user_id=current_user.id, **safe_params)`.
- **Impact:** If filters ever include client data, logs would contain unencrypted PII.

---

### 🟡 MEDIUM SEVERITY

**CSV Injection Vulnerability**
- **Affected:** `services.py:export_report_data()` (inferred from `routes.py:export_applications_report`)
- **Pattern:** Direct CSV export without formula sanitization
- **Fix:** Prepend dangerous characters (`=`, `+`, `-`, `@`, `\t`, `\r`) with single quote (`'`) or tab. Use `def sanitize_csv_field(value: str) -> str:` wrapper.
- **CVE:** CVE-2021-25292 (CSV formula injection)

**Bare Exception Handling**
- **Affected:** `routes.py` – All `except Exception as e` blocks
- **Pattern:** Catches and logs generic exceptions, potentially hiding security events
- **Fix:** Replace with specific exception handlers: `except (AppException, SQLAlchemyError) as e:`. Log security events with `logger.warning("security_event", error_code=e.error_code, user_id=...)`.

**Missing Rate Limiting**
- **Affected:** `routes.py` – All endpoints
- **Pattern:** No `@limiter.limit()` or similar decorators
- **Fix:** Add rate limiting: `@limiter.limit("10/minute")` for reports, `5/minute` for exports. Use Redis-backed limiter to prevent DoS and data scraping.

---

### 🟢 LOW SEVERITY

**Timezone-Aware Timestamps**
- **Affected:** `services.py` – `datetime.utcnow()` usage
- **Pattern:** Naive datetime objects
- **Fix:** Replace with `datetime.now(timezone.utc)` and ensure models use `DateTime(timezone=True)`.

**Index Completeness**
- **Affected:** `models.py:ReportExportLog`
- **Pattern:** Composite index on `(user_id, report_type)` but no single index on `export_timestamp`
- **Fix:** Add `Index('ix_report_export_timestamp', 'export_timestamp')` for time-range queries.

---

### 📋 MANDATORY REMEDIATION STEPS

1. **Add authentication** to all endpoints before any other changes
2. **Implement authorization** checks using user roles (broker, client, admin)
3. **Add missing audit fields** to all models to meet FINTRAC requirements
4. **Sanitize all logs** – grep for `logger.*filters` and `logger.*error.*str(e)` patterns
5. **Validate `filters` parameter** with strict schema
6. **Add rate limiting** to prevent abuse
7. **Implement CSV sanitization** before export
8. **Run `pip-audit`** and update dependencies

**Compliance Status:** Fails OSFI B-20 (no stress test logging in reports), FINTRAC (incomplete audit trail), PIPEDA (potential PII leakage).