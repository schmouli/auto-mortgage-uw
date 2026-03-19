**BLOCKED** – Critical security vulnerabilities identified that violate OSFI B-20, FINTRAC, and PIPEDA requirements.

---

### 🔴 CRITICAL FINDINGS

#### 1. **Missing Authentication & Authorization (CWE-306)**
**Severity:** CRITICAL  
**Affected Files:** `routes.py` (all endpoints)  
**Vulnerable Code Pattern:**
```python
# No authentication dependency on any endpoint
@router.post("/calculate", response_model=UnderwritingResultBase)
async def calculate_qualification(
    payload: UnderwritingCalculationRequest,
    db: AsyncSession = Depends(get_async_session)
) -> UnderwritingResultBase:
```
**Regulatory Impact:** Violates FINTRAC identity verification logging and PIPEDA access control requirements.  
**Recommended Fix:** 
```python
from mortgage_underwriting.common.security import get_current_user

@router.post("/calculate", response_model=UnderwritingResultBase)
async def calculate_qualification(
    payload: UnderwritingCalculationRequest,
    current_user: User = Depends(get_current_user),  # Add auth
    db: AsyncSession = Depends(get_async_session)
) -> UnderwritingResultBase:
```

#### 2. **Insecure Direct Object Reference (IDOR) – CWE-284**
**Severity:** CRITICAL  
**Affected Files:** `routes.py`, `services.py`  
**Vulnerable Code Pattern:**
```python
# routes.py - No ownership verification
@router.get("/applications/{result_id}/result", ...)
async def get_underwriting_result(result_id: int, ...):
    result = await service.get_result(result_id)  # No user filter

# services.py - No authorization check
async def get_result(self, result_id: int) -> Optional[UnderwritingResult]:
    stmt = select(UnderwritingResult).where(UnderwritingResult.id == result_id)
```
**Regulatory Impact:** Brokers/clients can access any underwriting result, violating PIPEDA data minimization.  
**Recommended Fix:** 
```python
# Add user_id filter and ownership check
stmt = select(UnderwritingResult).join(Application).where(
    UnderwritingResult.id == result_id,
    Application.user_id == current_user.id  # Enforce ownership
)
```

---

### 🟠 HIGH SEVERITY FINDINGS

#### 3. **PII Exposure in Logs (CWE-532)**
**Severity:** HIGH  
**Affected Files:** `services.py`  
**Vulnerable Code Pattern:**
```python
logger.info("underwriting_calculation_started", property_value=float(payload.property_value))
logger.error("underwriting_calculation_failed", error=str(e))  # Could leak PII in error trace
```
**Regulatory Impact:** Potential PIPEDA violation if ValidationError contains income/banking details.  
**Recommended Fix:** 
```python
# Use correlation_id only, never log financial values
logger.info("underwriting_calculation_started", correlation_id=correlation_id)
# Sanitize error messages
logger.error("underwriting_calculation_failed", error_code="CALC_ERROR", correlation_id=correlation_id)
```

#### 4. **Cascade Delete Violates FINTRAC Retention**
**Severity:** HIGH  
**Affected Files:** `models.py`  
**Vulnerable Code Pattern:**
```python
application_id: Mapped[int] = mapped_column(
    ForeignKey("applications.id", ondelete="CASCADE"),  # Violates 5-year retention
    nullable=False
)
```
**Regulatory Impact:** FINTRAC requires immutable 5-year retention; CASCADE delete destroys audit trail.  
**Recommended Fix:** 
```python
# Use RESTRICT or SET NULL with soft-delete pattern
ForeignKey("applications.id", ondelete="RESTRICT")
# Implement soft-delete: add is_deleted flag, never hard delete
```

#### 5. **Missing Rate Limiting & Security Headers**
**Severity:** HIGH  
**Affected Files:** `routes.py`  
**Vulnerable Code Pattern:** No rate limiting or security middleware configured.  
**Recommended Fix:** 
```python
# Add to FastAPI app main module
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/calculate", response_model=UnderwritingResultBase)
@limiter.limit("10/minute")  # Prevent brute force
async def calculate_qualification(...):
```

---

### 🟡 MEDIUM SEVERITY FINDINGS

#### 6. **Insufficient Input Validation**
**Severity:** MEDIUM  
**Affected Files:** `schemas.py`  
**Vulnerable Code Pattern:**
```python
# Missing max_length on string fields that could be abused
decision: Mapped[str] = mapped_column(String(20), nullable=False)
reason: Mapped[str] = mapped_column(Text, nullable=False)  # No length limit in model
```
**Recommended Fix:** 
```python
reason: Mapped[str] = mapped_column(Text, nullable=False)  # Keep Text
# But in schema:
reason: str = Field(..., min_length=10, max_length=1000)  # Already present, good
```

#### 7. **Floating Point Conversion in Logs**
**Severity:** MEDIUM  
**Affected Files:** `services.py`  
**Vulnerable Code Pattern:**
```python
logger.info("underwriting_calculation_completed", 
           gds_ratio=float(result.gds_ratio),  # Precision loss
           tds_ratio=float(result.tds_ratio))
```
**Regulatory Impact:** OSFI B-20 auditability requires exact Decimal precision.  
**Recommended Fix:** 
```python
logger.info("underwriting_calculation_completed", 
           gds_ratio=str(result.gds_ratio),  # Preserve precision
           tds_ratio=str(result.tds_ratio))
```

---

### ✅ COMPLIANT AREAS

- **OSFI B-20:** Stress test calculation correct; GDS/TDS constraints enforced via database checks
- **CMHC:** LTV calculation uses Decimal; premium tier lookup implemented correctly
- **SQL Injection:** Proper ORM usage, no raw SQL concatenation
- **Secrets Management:** No hardcoded secrets detected in provided code

---

### FINAL VERDICT

**BLOCKED** – The module cannot be deployed due to critical authentication/authorization failures that violate FINTRAC identity verification requirements and PIPEDA access controls. The cascade delete pattern also risks destroying mandatory financial records.

**Required Actions Before Approval:**
1. Implement JWT authentication on all endpoints with `get_current_user` dependency
2. Add ownership verification to prevent IDOR attacks
3. Replace cascade delete with soft-delete pattern for FINTRAC compliance
4. Sanitize all logging to exclude financial values and PII
5. Add rate limiting and security headers middleware
6. Conduct penetration testing focusing on broken access control scenarios