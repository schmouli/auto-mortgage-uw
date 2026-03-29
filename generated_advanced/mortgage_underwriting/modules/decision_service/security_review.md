**BLOCKED** – Critical security vulnerabilities identified. Remediation required before production deployment.

---

### 🔴 CRITICAL FINDINGS

#### 1. **Broken Authentication & Authorization (CWE-306, CWE-284)**
- **Severity**: CRITICAL  
- **Affected Files**: `routes.py` (all endpoints), `services.py`  
- **Vulnerable Code Pattern**:  
  ```python
  # routes.py - No auth dependency
  async def evaluate_decision(payload: DecisionEvaluateRequest, service: ...)
  
  # services.py - No ownership verification
  async def get_decision(self, application_id: UUID)
  ```  
- **Risk**: All endpoints are publicly accessible. Attackers can read, create, and audit any mortgage decision without authentication.  
- **Recommended Fix**:  
  ```python
  # Add to ALL endpoints
  user: Annotated[User, Depends(get_current_user)]
  
  # Add ownership check in services
  if record.application_id not in user.authorized_applications:
      raise ForbiddenException()
  ```

#### 2. **Insecure Direct Object Reference (IDOR) (CWE-639)**
- **Severity**: CRITICAL  
- **Affected Files**: `routes.py`, `services.py`  
- **Vulnerable Code Pattern**:  
  ```python
  # routes.py
  @router.get("/{application_id}")
  async def get_decision_record(application_id: UUID, ...)
  ```  
- **Risk**: Any user can access any application's decision data and audit trail by iterating UUIDs. Violates PIPEDA data minimization principle.  
- **Recommended Fix**: Implement tenant isolation:  
  ```python
  # In service layer
  stmt = select(DecisionRecord).where(
      DecisionRecord.application_id == application_id,
      DecisionRecord.created_by == user.id  # Add created_by column
  )
  ```

#### 3. **PII Leakage via Logging (CWE-532)**
- **Severity**: HIGH  
- **Affected Files**: `services.py:82`  
- **Vulnerable Code Pattern**:  
  ```python
  logger.info("decision_evaluate_complete", 
             gds=float(gds),  # Converts Decimal to float
             tds=float(tds))  # Financial ratios leaked
  ```  
- **Risk**: Violates "NEVER use float for money" rule. Financial ratios are PII under PIPEDA. Logs may be stored insecurely or shared.  
- **Recommended Fix**:  
  ```python
  logger.info("decision_evaluate_complete",
             application_id=payload.application_id,
             decision=decision,
             # Remove gds/tds from logs or hash them
             audit_hash=hashlib.sha256(f"{gds}{tds}".encode()).hexdigest())
  ```

---

### 🟡 HIGH SEVERITY FINDINGS

#### 4. **Information Disclosure via Generic Exception Handling (CWE-200)**
- **Severity**: HIGH  
- **Affected Files**: `routes.py:28`, `routes.py:44`, `routes.py:58`  
- **Vulnerable Code Pattern**:  
  ```python
  except Exception as e:
      raise HTTPException(detail={"message": str(e)})  # May leak stack traces
  ```  
- **Risk**: Internal errors (database connection strings, file paths) may be exposed to clients.  
- **Recommended Fix**:  
  ```python
  except AppException as e:
      logger.error("decision_error", error=str(e))
      raise HTTPException(status_code=400, detail={"error_code": "DECISION_ERROR"})
  ```

#### 5. **Missing Rate Limiting (CWE-770)**
- **Severity**: HIGH  
- **Affected Files**: `routes.py`  
- **Risk**: Endpoints vulnerable to brute-force attacks and DoS. Attackers could flood system with fake applications or scrape entire database.  
- **Recommended Fix**: Add FastAPI rate limiting middleware:  
  ```python
  from slowapi import Limiter
  limiter = Limiter(key_func=get_remote_address)
  
  @router.post("/evaluate")
  @limiter.limit("10/minute")
  ```

---

### 🟢 MEDIUM SEVERITY FINDINGS

#### 6. **Missing Security Headers (CWE-693)**
- **Severity**: MEDIUM  
- **Affected Files**: `routes.py`  
- **Risk**: No HSTS, CSP, X-Frame-Options headers. Vulnerable to clickjacking, XSS, and protocol downgrade attacks.  
- **Recommended Fix**: Add middleware:  
  ```python
  @app.middleware("http")
  async def add_security_headers(request, call_next):
      response = await call_next(request)
      response.headers["Strict-Transport-Security"] = "max-age=31536000"
      response.headers["Content-Security-Policy"] = "default-src 'self'"
      return response
  ```

#### 7. **Insufficient Input Validation on UUID Path Parameter**
- **Severity**: MEDIUM  
- **Affected Files**: `routes.py:37`, `routes.py:50`  
- **Vulnerable Code Pattern**:  
  ```python
  @router.get("/{application_id}")  # No extra validation
  ```  
- **Risk**: While FastAPI validates UUID format, no check exists for UUID version or tenant scoping.  
- **Recommended Fix**: Add custom validator to ensure UUIDv4 and tenant prefix:  
  ```python
  class ApplicationUUID(UUID4):
      @classmethod
      def validate(cls, value):
          if not str(value).startswith(user.tenant_prefix):
              raise ValueError("Invalid application ID")
  ```

---

### ✅ REGULATORY COMPLIANCE STATUS

| Requirement | Status | Notes |
|-------------|--------|-------|
| **OSFI B-20 Stress Test** | ✅ COMPLIANT | Correctly implements `max(rate+2%, 5.25%)` |
| **GDS/TDS Limits** | ✅ COMPLIANT | Enforces 39%/44% thresholds |
| **FINTRAC Audit Trail** | ✅ COMPLIANT | Immutable records with `created_at`, no DELETE |
| **CMHC Insurance Logic** | ✅ COMPLIANT | LTV > 80% triggers `cmhc_required=True` |
| **PIPEDA Encryption** | ⚠️ PARTIAL | No PII stored in model, but raw income in request payload not encrypted at rest |

---

### 📋 REMEDIATION ROADMAP

1. **Immediate (Blocker)**: Implement JWT authentication + tenant isolation
2. **Immediate (Blocker)**: Remove financial ratios from logs; use Decimal throughout
3. **Before QA**: Add rate limiting and security headers
4. **Before Prod**: Implement specific exception handling; add `created_by` column for ownership

**Estimated Remediation Effort**: 2-3 days