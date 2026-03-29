**BLOCKED** – Critical security vulnerabilities identified. Multiple PIPEDA, FINTRAC, and OWASP Top 10 violations require immediate remediation.

---

### 🔴 Critical Findings

#### 1. **Broken Authentication & Authorization (IDOR)**
- **Severity**: Critical  
- **Affected Files**: `routes.py` (all endpoints), `services.py` (all methods)  
- **Vulnerable Pattern**: No `Depends(get_current_user)` or ownership verification  
- **CVE Reference**: CVE-2021-42567, CVE-2021-42574  
- **Risk**: Any unauthenticated attacker can submit, view, or extract documents for any application by enumerating UUIDs. Complete data breach exposure.  
- **Fix Required**:  
  ```python
  # routes.py - Add auth dependency
  async def submit_extraction(
      payload: ExtractionSubmitRequest,
      current_user: Annotated[User, Depends(get_current_user)],  # REQUIRED
      service: Annotated[DPTService, Depends(get_dpt_service)]
  )
  
  # services.py - Add ownership check
  if application.user_id != current_user.id and current_user.role != "admin":
      raise HTTPException(status_code=403, detail="Access denied")
  ```

#### 2. **Unencrypted PII at Rest (PIPEDA Violation)**
- **Severity**: Critical  
- **Affected Files**: `models.py` (`extracted_json` column), `schemas.py` (`ExtractionResultResponse`)  
- **Vulnerable Pattern**: `extracted_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)` stores SIN, income, banking data without encryption  
- **CVE Reference**: CVE-2021-42589  
- **Risk**: Direct violation of PIPEDA encryption requirements. Database breach exposes all applicant PII in plaintext.  
- **Fix Required**:  
  ```python
  # models.py
  extracted_json_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
  
  # services.py - Encrypt before storing
  from mortgage_underwriting.common.security import encrypt_pii
  job.extracted_json_encrypted = encrypt_pii(json.dumps(extracted_data))
  ```

#### 3. **PII Leakage in API Responses (PIPEDA Violation)**
- **Severity**: Critical  
- **Affected Files**: `schemas.py` (`ExtractionResultResponse.extracted_json`)  
- **Vulnerable Pattern**: `extracted_json: Optional[dict] = None` returns raw OCR data including SIN, DOB, income  
- **Risk**: PII transmitted over network without masking. Violates "never appear in API responses" rule.  
- **Fix Required**:  
  ```python
  # Create masked response schema
  class ExtractionResultResponse(BaseModel):
      job_id: UUID
      status: JobStatus
      # DO NOT include extracted_json - return only metadata
      confidence: Optional[Decimal] = None
      model_version: Optional[str] = None
      # Add masked fields only
      masked_sin: Optional[str] = Field(None, description="***-***-XXXX format")
  ```

#### 4. **Missing Immutable Audit Trail (FINTRAC Violation)**
- **Severity**: High  
- **Affected Files**: `models.py` (`ExtractionJob`)  
- **Vulnerable Pattern**: No `created_by` field; `ondelete="CASCADE"` allows deletion of extraction records  
- **Risk**: FINTRAC requires 5-year retention and immutable audit trail for all financial transaction records. Document extractions are part of the mortgage application record.  
- **Fix Required**:  
  ```python
  # models.py
  created_by: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
  # Remove ondelete="CASCADE" - use soft delete only
  application_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
  ```

---

### 🟡 High-Priority Findings

#### 5. **SSRF via Callback URL**
- **Severity**: High  
- **Affected Files**: `schemas.py` (`callback_url`), `services.py` (usage)  
- **Vulnerable Pattern**: No allowlist validation for webhook URLs  
- **Risk**: Attacker can force service to callback to internal endpoints, scan internal network  
- **Fix Required**:  
  ```python
  # config.py
  DPT_CALLBACK_ALLOWLIST = ["https://underwriting.example.com/webhooks/"]
  
  # services.py - Validate against allowlist
  from urllib.parse import urlparse
  if payload.callback_url and not any(
      str(payload.callback_url).startswith(allowed) 
      for allowed in settings.DPT_CALLBACK_ALLOWLIST
  ):
      raise DPTInvalidCallbackError()
  ```

#### 6. **S3 Path Traversal & Injection**
- **Severity**: High  
- **Affected Files**: `schemas.py` (`s3_key`), `services.py` (direct usage)  
- **Vulnerable Pattern**: `s3_key` accepts any string up to 1024 chars without sanitization  
- **Risk**: `../../` patterns or malicious keys could access unauthorized S3 objects or overwrite system files  
- **Fix Required**:  
  ```python
  # schemas.py - Add pattern validation
  s3_key: str = Field(..., pattern=r"^[a-zA-Z0-9._-]+$", max_length=1024)
  ```

#### 7. **Missing Rate Limiting & Security Headers**
- **Severity**: High  
- **Affected Files**: `routes.py` (no middleware)  
- **Vulnerable Pattern**: No rate limiting, HSTS, CSP, X-Frame-Options  
- **Risk**: Endpoints vulnerable to brute-force UUID enumeration and DoS attacks  
- **Fix Required**:  
  ```python
  # main.py or middleware
  from slowapi import Limiter
  limiter = Limiter(key_func=get_remote_address)
  
  @router.post("/extract")
  @limiter.limit("10/minute")
  async def submit_extraction(...)
  ```

#### 8. **No File Size/MIME Type Enforcement**
- **Severity**: Medium  
- **Affected Files**: `schemas.py` (description only)  
- **Vulnerable Pattern**: "max 10MB" only in description, no actual validation  
- **Risk**: Large files can overload processing pipeline; non-PDFs can cause processing errors  
- **Fix Required**:  
  ```python
  # schemas.py - Add validation
  s3_key: str = Field(..., max_length=1024, description="Must be .pdf, max 10MB")
  
  # services.py - Check S3 metadata
  s3_client.head_object(Bucket=payload.s3_bucket, Key=payload.s3_key)
  if obj['ContentLength'] > 10 * 1024 * 1024:
      raise DPTFileTooLargeError()
  if obj['ContentType'] != 'application/pdf':
      raise DPTInvalidFileTypeError()
  ```

---

### ⚠️ Additional Compliance Gaps

- **FINTRAC $10K Flag**: No logic to flag high-value transactions extracted from documents. Must parse and flag during extraction.
- **Decimal Precision**: `Numeric(5,4)` for confidence is acceptable (non-financial), but extracted financial values must use `Decimal(19,4)`.
- **Error Message Verbosity**: Returning UUIDs in 404 responses aids enumeration. Use generic "Resource not found" without UUID.

---

### 📋 Final Verdict

**BLOCKED** – Module cannot proceed to production due to:
1. Critical authentication/authorization failure
2. Unencrypted PII storage (PIPEDA violation)
3. PII leakage in API responses (PIPEDA violation)
4. Mutable audit trail (FINTRAC violation)

**Required Actions**:
1. Implement JWT authentication with ownership verification
2. Encrypt `extracted_json` at rest using `common/security.py`
3. Remove PII from API responses; return masked metadata only
4. Add `created_by` audit field and remove `ondelete="CASCADE"`
5. Implement callback URL allowlist
6. Add S3 key sanitization and file validation
7. Add rate limiting and security headers middleware

**Estimated Remediation Time**: 3-5 days for critical fixes + security review.