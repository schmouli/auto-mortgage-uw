**BLOCKED** – Critical security vulnerabilities and regulatory violations identified.

---

### 🔴 CRITICAL SEVERITY

**1. Missing Authentication & Authorization (IDOR)**  
- **Affected Files:** `routes.py` (all endpoints), `services.py` (all methods)  
- **Vulnerable Pattern:** No `Depends(get_current_user)` or ownership validation. `user_id` passed as query parameter without JWT verification.  
- **Exploit:** Any attacker can upload, view, verify, or delete documents for any `application_id`.  
- **Regulatory Impact:** **FINTRAC** violation – no identity verification logging for document access.  
- **CWE:** CWE-284 (Improper Access Control), CWE-287 (Improper Authentication)  
- **Fix:** Implement `Depends(get_current_user)` on all endpoints; add `application.user_id` ownership check in service layer.

**2. PII Not Encrypted at Rest**  
- **Affected Files:** `models.py` (`Document.file_path`), `services.py` (`upload_document`)  
- **Vulnerable Pattern:** Documents containing SIN, income, banking data stored as plain files. No AES-256 encryption before storage.  
- **Exploit:** Direct filesystem access exposes sensitive customer PII.  
- **Regulatory Impact:** **PIPEDA** violation – SIN/income must be encrypted at rest.  
- **CWE:** CWE-522 (Insufficiently Protected Credentials)  
- **Fix:** Encrypt file content using `common/security.encrypt_pii()` before writing to disk; store encryption metadata separately.

**3. Hard Delete Violates FINTRAC Retention**  
- **Affected Files:** `services.py:delete_document()`  
- **Vulnerable Pattern:** `await self.db.delete(doc)` permanently removes financial records.  
- **Regulatory Impact:** **FINTRAC** 5-year retention requirement violated.  
- **Fix:** Implement soft-delete (`is_deleted` flag + `deleted_at` timestamp); block DELETE on financial docs after 24h.

---

### 🟠 HIGH SEVERITY

**4. Bare Except Clauses Leak Stack Traces**  
- **Affected Files:** `routes.py` (all 7 endpoints)  
- **Vulnerable Pattern:** `except Exception as e: raise HTTPException(detail={"detail": str(e)})`  
- **Exploit:** Can expose database connection strings, internal paths, or PII in error messages.  
- **CWE:** CWE-703 (Improper Check of Exceptional Conditions)  
- **Fix:** Catch specific exceptions (`AppException`, `NotFoundError`); use generic "Internal error" message for unknown exceptions.

**5. Missing Virus/Malware Scanning**  
- **Affected Files:** `services.py:upload_document()`  
- **Vulnerable Pattern:** `logger.info("file_virus_scan_placeholder")` – no actual scan implementation.  
- **Exploit:** Malicious PDFs/JPEGs can compromise underwriter systems.  
- **Fix:** Integrate ClamAV or commercial scanner; block upload until scan passes.

**6. Path Traversal via Document Type**  
- **Affected Files:** `services.py:upload_document()`  
- **Vulnerable Pattern:** `file_path = f"/uploads/{application_id}/{payload.document_type}/{safe_filename}"`  
- **Exploit:** If `document_type` is compromised, attacker could write outside `/uploads`.  
- **CWE:** CWE-22 (Path Traversal)  
- **Fix:** Validate `document_type` against `DocumentType` enum; use `pathlib.Path` with `.resolve().relative_to(base_dir)` check.

---

### 🟡 MEDIUM SEVERITY

**7. Insufficient Filename Sanitization**  
- **Affected Files:** `services.py:upload_document()`  
- **Vulnerable Pattern:** `safe_filename = ''.join(c for c in payload.file_name if c.isalnum() or c in (' ', '.', '_'))`  
- **Exploit:** Allows multiple dots (`file.txt.exe`) or Unicode homoglyphs; spaces cause shell escaping issues.  
- **Fix:** Use `pathvalidate` library; replace spaces with underscores; enforce single extension.

**8. File Size DoS via Multiple Uploads**  
- **Affected Files:** `routes.py:upload_document()`  
- **Vulnerable Pattern:** No rate limiting on uploads; validates single file size but not upload frequency.  
- **Exploit:** Attacker can exhaust storage with rapid uploads.  
- **Fix:** Add rate limiter (e.g., 10 uploads/minute per user); implement quota per application.

**9. PII in API Responses**  
- **Affected Files:** `schemas.py:DocumentResponse`  
- **Vulnerable Pattern:** `file_name` and `file_path` returned directly; may contain SIN in filename (e.g., `sin_123456789.pdf`).  
- **Fix:** Mask filenames in list view; return full path only on download endpoint.

---

### 🔵 LOW SEVERITY

**10. Missing Security Headers**  
- **Affected Files:** `routes.py` (global config)  
- **Vulnerable Pattern:** No HSTS, CSP, X-Frame-Options, X-Content-Type-Options configured.  
- **Fix:** Add middleware: `CSP: default-src 'self'`, `X-Frame-Options: DENY`, `Strict-Transport-Security: max-age=63072000`.

---

### 📋 REGULATORY COMPLIANCE SUMMARY

| Requirement | Status | Violation |
|-------------|--------|-----------|
| **OSFI B-20** | N/A | No financial calculations in this module |
| **FINTRAC** | ❌ **FAILED** | Hard delete; no identity verification logging |
| **CMHC** | N/A | No LTV/insurance logic |
| **PIPEDA** | ❌ **FAILED** | PII in documents not encrypted |

---

### ✅ MANDATORY REMEDIATION STEPS

1. **Authentication:** Add `JWTBearer` dependency to all routes; extract `user_id` from token claims.
2. **Authorization:** In `DocumentService`, verify `application.user_id == current_user.id` or admin role.
3. **Encryption:** Wrap file I/O with `encrypt_pii()` / `decrypt_pii()` from `common/security.py`.
4. **Soft Delete:** Replace `db.delete()` with `doc.is_deleted = True`; add retention policy cron job.
5. **Error Handling:** Replace bare `except` with explicit exception handlers; log internally, return generic messages.
6. **Virus Scan:** Implement actual scanning before `db.commit()`; reject on failure.
7. **Rate Limiting:** Add `limiter = Limiter(key_func=get_remote_address)` on upload endpoint.
8. **Security Headers:** Configure `fastapi.middleware.TrustedHostMiddleware` and custom CSP.

**Deploy Blocker:** Remediate all CRITICAL and HIGH findings before merge.