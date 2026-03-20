**BLOCKED** – Critical security vulnerabilities and regulatory non-compliance detected.

---

### Critical Findings (Production Blockers)

#### 1. **Missing Authentication & Authorization (IDOR)**
- **Severity**: CRITICAL | **CWE-284: Improper Access Control**
- **Affected**: All endpoints in `routes.py`
- **Vulnerable Pattern**: No `Depends(get_current_user)` or role checks
- **Exploit**: Any actor can submit, view, or modify any application/document by iterating IDs
- **Regulatory Impact**: Violates FINTRAC identity verification logging requirements
- **Fix**: Implement JWT authentication with role-based access control (broker, client, admin) and enforce ownership checks on every endpoint

#### 2. **PII Leakage in Logs (PIPEDA Violation)**
- **Severity**: CRITICAL | **CWE-532: Information Exposure Through Log Files**
- **Affected**: `services.py:63, 71`
```python
logger.warning("duplicate_active_application", sin_hash=sin_hash)  # PII!
logger.error("borrower_creation_failed", sin_hash=sin_hash)        # PII!
```
- **Risk**: SIN hashes are indirect identifiers; combined with other data, they enable re-identification
- **Fix**: Remove all PII from logs; use `correlation_id` only for tracing

#### 3. **Unencrypted PII at Rest (PIPEDA Violation)**
- **Severity**: CRITICAL
- **Affected**: `models.py` – `Borrower.full_name`, `Borrower.gross_income`, `Borrower.credit_score`
- **Regulatory Impact**: Direct violation of PIPEDA encryption requirement for sensitive personal information
- **Fix**: Encrypt all PII fields using `encrypt_pii()`; store only hashed values for indexing

#### 4. **No Immutable Audit Trail (FINTRAC Violation)**
- **Severity**: CRITICAL
- **Affected**: All models lack `created_by`, `updated_by`; no audit log tables
- **Regulatory Impact**: FINTRAC requires immutable records (who/when/what) for 5-year retention
- **Fix**: Add `created_by: Mapped[str]` to all models; create separate audit tables with INSERT-only permissions

#### 5. **No OSFI B-20 Stress Test Implementation**
- **Severity**: CRITICAL
- **Affected**: `services.py` – missing GDS/TDS calculation logic
- **Regulatory Impact**: OSFI B-20 mandates qualifying_rate = max(contract_rate + 2%, 5.25%) and hard limits (GDS ≤ 39%, TDS ≤ 44%)
- **Fix**: Implement GDS/TDS calculation service with auditable logging; enforce limits before application submission

#### 6. **No FINTRAC >$10K Transaction Flagging**
- **Severity**: CRITICAL
- **Affected**: `models.py` – missing `transaction_amount` field
- **Regulatory Impact**: FINTRAC requires explicit flagging and reporting of transactions > CAD $10,000
- **Fix**: Add `transaction_amount: Mapped[Decimal]` to `Application`; auto-set `transaction_reported` flag

#### 7. **Missing Soft Delete (FINTRAC Retention Violation)**
- **Severity**: HIGH
- **Affected**: All models use `ondelete="CASCADE"`; no `is_deleted` flag
- **Regulatory Impact**: FINTRAC mandates 5-year retention; hard DELETE violates this
- **Fix**: Add `is_deleted: Mapped[bool] = False` and `deleted_at: Mapped[Optional[datetime]]` to all models; replace DELETE with UPDATE queries

#### 8. **Unvalidated File Uploads**
- **Severity**: HIGH | **CWE-434: Unrestricted File Upload**
- **Affected**: `schemas.py:42` – `file_content: bytes` with no validation
- **Missing Controls**: 
  - No MIME type validation (allows executables)
  - No file size enforcement (10MB mentioned but not enforced)
  - No virus scanning integration
- **Fix**: Add `file_validator()`; integrate ClamAV/ScanAPI; enforce `max_length=10*1024*1024`

#### 9. **Bare Except Clauses (Security Misconfiguration)**
- **Severity**: HIGH | **CWE-396: Declaration of Catch for Generic Exception**
- **Affected**: All endpoints in `routes.py` and `services.py:90`
- **Risk**: Can mask security exceptions, leak stack traces, cause DoS
- **Fix**: Replace `except Exception` with specific exceptions (`AppException`, `IntegrityError`, etc.)

#### 10. **No Rate Limiting (DoS Risk)**
- **Severity**: HIGH | **CWE-770: Allocation of Resources Without Limits**
- **Affected**: All endpoints
- **Exploit**: Application flooding, brute force attacks, scraping
- **Fix**: Implement `slowapi` or `fastapi-limiter` with user/IP-based limits

---

### High Severity Findings

#### 11. **Missing `updated_at` on Borrower & Document Models**
- **Affected**: `models.py` – `Borrower`, `Document` lack `updated_at`
- **Violation**: Project convention "ALWAYS include created_at, updated_at"
- **Fix**: Add `updated_at: Mapped[datetime]` with `onupdate=func.now()`

#### 12. **Test Database Mismatch**
- **Affected**: `conftest.py:12` – SQLite vs production PostgreSQL
- **Risk**: Hides PostgreSQL-specific issues (ENUM types, precision, concurrency)
- **Fix**: Use `postgresql+asyncpg://postgres:postgres@test-db:5432/test_db` in CI

#### 13. **No Security Headers**
- **Affected**: `routes.py` – no HSTS, CSP, X-Frame-Options
- **Fix**: Add middleware:
```python
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["X-Frame-Options"] = "DENY"
    return response
```

#### 14. **Transaction Type Free Text (FINTRAC Data Quality)**
- **Affected**: `schemas.py:89` – `transaction_type: str`
- **Fix**: Convert to `Enum` with FINTRAC-specified types (`electronic`, `cash`, etc.)

---

### Regulatory Compliance Summary

| Regulation | Status | Deficiencies |
|------------|--------|--------------|
| **OSFI B-20** | ❌ **NON-COMPLIANT** | No GDS/TDS, no stress test, no ratio logging |
| **FINTRAC** | ❌ **NON-COMPLIANT** | No immutable audit, no >$10K flag, no 5-year retention |
| **CMHC** | ❌ **NON-COMPLIANT** | No LTV-based insurance logic |
| **PIPEDA** | ❌ **NON-COMPLIANT** | Unencrypted PII fields, PII in logs |

---

### Recommended Remediation Order

1. **Implement JWT Auth + RBAC** (blocks all IDOR)
2. **Encrypt ALL PII fields** (PIPEDA compliance)
3. **Remove PII from logs** (security + PIPEDA)
4. **Add audit trail tables** (FINTRAC compliance)
5. **Implement OSFI B-20 calculator service** (regulatory)
6. **Add FINTRAC transaction flagging** (regulatory)
7. **Add soft delete to all models** (FINTRAC retention)
8. **Implement file upload validation** (security)
9. **Add rate limiting** (DoS protection)
10. **Replace bare except clauses** (security)
11. **Use PostgreSQL in tests** (reliability)
12. **Add security headers** (defense in depth)

---

### CVE References
- **CVE-2023-23752**: Improper access check pattern similar to IDOR vulnerabilities
- **CWE-284**: Improper Access Control (applies to all endpoints)
- **CWE-532**: Information Exposure Through Log Files (PII leakage)
- **CWE-434**: Unrestricted File Upload (document handling)

**Final Action**: **BLOCKED** – Do not deploy. Remediate critical findings and re-audit.