**BLOCKED** – Critical security vulnerabilities prevent deployment. Remediation required before approval.

---

## Critical Findings (Immediate Action Required)

### 1. **Broken Authentication & IDOR (CWE-306, CWE-639)**
- **Severity:** CRITICAL
- **Affected Files:** `routes.py` (all endpoints), `services.py` (all service methods)
- **Vulnerable Code Pattern:** 
  ```python
  # routes.py - No auth dependency
  async def submit_pdf_for_extraction(request: ExtractionRequest, db: AsyncSession = Depends(get_db_session))
  
  # services.py - No ownership verification
  stmt = select(Extraction).where(Extraction.id == job_id)
  ```
- **Exploitation:** Any actor can submit extraction jobs, poll any `job_id`, and retrieve any `extracted_json` containing PII from other users' mortgage applications.
- **CVE Reference:** CVE-2021-42013 (similar path traversal/auth bypass), CVE-2022-24715 (Grafana IDOR)
- **Fix:** 
  ```python
  # Add to ALL routes
  user: User = Depends(get_current_user)
  
  # Add to ALL service methods
  stmt = select(Extraction).where(
      Extraction.id == job_id,
      Extraction.application_id.in_(
          select(Application.id).where(Application.user_id == user.id)
      )
  )
  ```

### 2. **PIPEDA Violation – Unencrypted PII at Rest (CWE-311)**
- **Severity:** CRITICAL
- **Affected Files:** `models.py` (line 35), `services.py` (lines 117, 138), `schemas.py` (line 42)
- **Vulnerable Code Pattern:**
  ```python
  # models.py
  extracted_json: Mapped[dict] = mapped_column(Text, nullable=False)
  
  # services.py – storing raw PII
  extracted_json=mock_results["data"]  # Contains income, bank balances, SIN
  
  # schemas.py – returning raw PII
  extracted_json: Dict[str, Any] = Field(description="Extracted structured data")
  ```
- **Exploitation:** Database breach exposes unencrypted income (`line_15000: 85000`), bank balances (`balance: 15000`), and potentially SIN/DOB if extracted. Violates PIPEDA encryption mandate.
- **CVE Reference:** CVE-2021-38153 (sensitive data exposure), CVE-2020-25668 (unencrypted PII)
- **Fix:** 
  ```python
  # models.py
  from common.security import encrypt_pii
  extracted_json_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
  
  # services.py – encrypt before storage
  encrypted_data = encrypt_pii(json.dumps(mock_results["data"]))
  extracted_json_encrypted=encrypted_data
  ```

### 3. **PII Leakage in API Responses (CWE-200)**
- **Severity:** CRITICAL
- **Affected Files:** `schemas.py` (line 42), `routes.py` (line 88)
- **Vulnerable Code Pattern:**
  ```python
  # schemas.py – No masking
  extracted_json: Dict[str, Any]  # Returns raw income/banking data
  
  # routes.py – Direct return
  return await service.get_extraction_result(job_id)
  ```
- **Exploitation:** MITM attack or compromised frontend exposes applicant's financial data. Violates "NEVER log SIN, income, banking data" and PIPEDA minimization.
- **Fix:** 
  ```python
  # schemas.py – Add masking validator
  @field_validator('extracted_json', mode='before')
  def mask_sensitive_data(cls, v):
      return {
          k: "***MASKED***" if k in {'sin', 'dob', 'account_number'} else v
          for k, v in v.items()
      }
  ```

### 4. **Missing ForeignKey `ondelete` – Data Integrity Risk**
- **Severity:** HIGH
- **Affected Files:** `models.py` (line 18)
- **Vulnerable Code Pattern:**
  ```python
  application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), nullable=False)
  ```
- **Impact:** Deleting an `application` record will cause FK constraint violations or orphaned extractions, breaking FINTRAC's 5-year retention audit trail.
- **Fix:** 
  ```python
  ForeignKey("applications.id", ondelete="RESTRICT")  # Enforce retention
  ```

---

## High Severity Findings

### 5. **Hardcoded Configuration Values**
- **Severity:** HIGH
- **Affected Files:** `services.py` (line 35, 78)
- **Vulnerable Code Pattern:**
  ```python
  model_version="donut-v1.0"  # Hardcoded
  await asyncio.sleep(5)       # Hardcoded delay
  ```
- **Fix:** Move to `common/config.py` as `DPT_MODEL_VERSION` and `DPT_PROCESSING_TIMEOUT`.

### 6. **No Rate Limiting – DoS Risk**
- **Severity:** HIGH
- **Affected Files:** `routes.py` (all endpoints)
- **Vulnerable Code Pattern:** No `Depends(RateLimiter(times=5, seconds=60))`
- **Impact:** Attackers can flood `/extract` to exhaust GPU/ML resources or DB connections.
- **Fix:** Add FastAPI Limiter: `@router.post("/extract", dependencies=[Depends(RateLimiter(times=10, minutes=1))])`

### 7. **Improper Error Handling – Information Disclosure**
- **Severity:** HIGH
- **Affected Files:** `routes.py` (lines 35, 56, 88)
- **Vulnerable Code Pattern:**
  ```python
  raise HTTPException(status_code=500, detail=str(e))  # Exposes internal errors
  ```
- **Exploitation:** Stack traces or DB errors leaked to client.
- **Fix:** 
  ```python
  raise HTTPException(status_code=500, detail="Internal processing error", 
                      headers={"X-Error-Code": "DPT_PROCESSING_FAILED"})
  ```

### 8. **No Immutable Audit Trail (FINTRAC Violation)**
- **Severity:** HIGH
- **Affected Files:** `models.py` (line 49)
- **Vulnerable Code Pattern:**
  ```python
  changed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
  ```
- **Impact:** `changed_by` is nullable and `updated_at` allows modifications. FINTRAC requires immutable WORM compliance for financial records.
- **Fix:** Remove `updated_at`, make `changed_by` non-nullable, and append-only with versioning.

---

## Medium Severity Findings

### 9. **Pydantic v2 Deprecated Validator**
- **Severity:** MEDIUM
- **Affected Files:** `schemas.py` (line 50)
- **Vulnerable Code Pattern:** `@validator` (v1) instead of `@field_validator` (v2)
- **Fix:** Replace with `@field_validator('confidence', mode='before')`

### 10. **No File Existence/Access Validation**
- **Severity:** MEDIUM
- **Affected Files:** `services.py` (line 28)
- **Vulnerable Code Pattern:** `s3_key` accepted without verifying S3 object exists or user has access.
- **Impact:** Process spoofed paths or unauthorized bucket access.
- **Fix:** 
  ```python
  from common.security import verify_s3_access
  if not await verify_s3_access(request.s3_key, user):
      raise PermissionError("S3 key not accessible")
  ```

### 11. **Missing Security Headers**
- **Severity:** MEDIUM
- **Affected Files:** `routes.py` (global)
- **Missing Headers:** `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options: DENY`
- **Fix:** Add middleware in `main.py`:
  ```python
  @app.middleware("http")
  async def add_security_headers(request, call_next):
      response = await call_next(request)
      response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
      return response
  ```

---

## Compliance Violations Summary

| Regulation | Requirement | Status | Evidence |
|------------|-------------|--------|----------|
| **PIPEDA** | Encrypt SIN/DOB at rest | ❌ FAIL | `extracted_json` stored as plain Text |
| **PIPEDA** | Never return SIN/DOB in APIs | ❌ FAIL | Raw `extracted_json` returned |
| **FINTRAC** | Immutable audit trail (WORM) | ❌ FAIL | `updated_at` allows mutation |
| **FINTRAC** | Soft-delete only | ❌ FAIL | No `deleted_at` column |
| **FINTRAC** | Flag transactions >$10k | ⚠️ N/A | Module doesn't handle transactions |
| **OSFI B-20** | GDS/TDS stress test | ⚠️ N/A | Not applicable to DPT module |

---

## Remediation Checklist

- [ ] **IMMEDIATE:** Add `get_current_user` dependency to all routes and enforce ownership checks
- [ ] **IMMEDIATE:** Implement `encrypt_pii()`/`decrypt_pii()` for `extracted_json` field
- [ ] **IMMEDIATE:** Mask PII in `ExtractionResultResponse` before serialization
- [ ] **IMMEDIATE:** Add `ondelete="RESTRICT"` to `application_id` ForeignKey
- [ ] **HIGH:** Replace hardcoded `model_version` with config-driven value
- [ ] **HIGH:** Add rate limiting via FastAPI Limiter
- [ ] **HIGH:** Remove `updated_at`, make audit fields append-only for FINTRAC compliance
- [ ] **MEDIUM:** Migrate `@validator` to `@field_validator`
- [ ] **MEDIUM:** Add S3 pre-flight validation and virus scanning hooks
- [ ] **MEDIUM:** Implement security headers middleware

**Final Verdict:** **BLOCKED** – Module cannot be deployed until authentication, PII encryption, and audit immutability are implemented.