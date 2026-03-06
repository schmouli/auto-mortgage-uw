# Underwriting Engine
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Underwriting Engine Design Plan

**File:** `docs/design/underwriting-engine.md`  
**Module:** `modules/underwriting/`  
**Version:** 1.0  
**Compliance:** OSFI B-20, FINTRAC, CMHC, PIPEDA

---

## 1. Endpoints

### 1.1 POST `/api/v1/underwriting/calculate`
**Purpose:** Run qualification calculation without persisting results (dry-run).

**Authentication:** Authenticated user (lender/underwriter role)

**Request Body Schema:**
```python
class UnderwritingCalculateRequest(BaseModel):
    # Income details
    gross_annual_income: Decimal  # Required, > 0
    self_employed: bool = False
    self_employed_income_2yr_avg: Optional[Decimal] = None  # Required if self_employed=True
    
    # Property details
    property_value: Decimal  # Required, > 0
    property_type: Literal["SINGLE_FAMILY", "CONDO", "MULTI_UNIT"]
    condo_monthly_fee: Optional[Decimal] = Decimal("0")
    
    # Loan details
    requested_loan_amount: Decimal  # Required, > 0
    contract_interest_rate: Decimal  # Required, > 0
    amortization_years: int = 25  # 5-30 years
    
    # Existing obligations
    monthly_non_mortgage_debts: Decimal = Decimal("0")  # Credit cards, loans, etc.
    monthly_heating_cost: Decimal = Decimal("150")  # Default $150
    monthly_property_tax: Decimal  # Required
    
    # Additional income
    monthly_rental_income: Optional[Decimal] = Decimal("0")
    rental_income_premium: Decimal = Decimal("0.50")  # Default 50% inclusion
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
```

**Response Schema:**
```python
class UnderwritingCalculateResponse(BaseModel):
    underwriting_result: UnderwritingResult  # See section 3 output structure
    calculation_breakdown: Dict[str, Decimal]  # Audit trail for ratios
    
    class Config:
        json_encoders = {Decimal: str}
```

**Error Responses:**
| HTTP | Error Code | Condition |
|------|------------|-----------|
| 422 | `UNDERWRITING_002` | Invalid input (negative values, missing required fields) |
| 422 | `UNDERWRITING_005` | Self-employed income validation failed |
| 400 | `UNDERWRITING_006` | Property value exceeds program limits ($1.5M+) |

---

### 1.2 POST `/api/v1/underwriting/applications/{id}/evaluate`
**Purpose:** Execute full underwriting evaluation and persist results.

**Authentication:** Authenticated underwriter role

**Request Body Schema:**
```python
class UnderwritingEvaluateRequest(BaseModel):
    # Same as UnderwritingCalculateRequest
    # Plus optional override flags for manual review
    manual_override_reason: Optional[str] = None
    override_gds_threshold: Optional[Decimal] = None  # Admin only
    override_tds_threshold: Optional[Decimal] = None  # Admin only
```

**Response Schema:**
```python
class UnderwritingEvaluateResponse(BaseModel):
    underwriting_id: UUID
    decision: DecisionEnum
    result: UnderwritingResult
    created_at: datetime
```

**Error Responses:**
| HTTP | Error Code | Condition |
|------|------------|-----------|
| 404 | `UNDERWRITING_001` | Application ID not found |
| 409 | `UNDERWRITING_003` | Application already evaluated |
| 403 | `UNDERWRITING_007` | User lacks underwriter role |
| 422 | `UNDERWRITING_002` | Validation failed (same as calculate) |

---

### 1.3 GET `/api/v1/underwriting/applications/{id}/result`
**Purpose:** Retrieve saved underwriting result.

**Authentication:** Authenticated user (lender/underwriter role)

**Request Body:** None

**Response Schema:**
```python
class UnderwritingResultResponse(BaseModel):
    underwriting_id: UUID
    application_id: UUID
    decision: DecisionEnum
    result: UnderwritingResult
    created_at: datetime
    created_by: str  # Hashed user ID (PIPEDA compliance)
    audit_log: List[Dict]  # Immutable trail of changes
```

**Error Responses:**
| HTTP | Error Code | Condition |
|------|------------|-----------|
| 404 | `UNDERWRITING_001` | Underwriting result not found |
| 403 | `UNDERWRITING_008` | User not authorized for this application |

---

### 1.4 POST `/api/v1/underwriting/applications/{id}/override`
**Purpose:** Admin override of underwriting decision with mandatory reason.

**Authentication:** Admin role only

**Request Body Schema:**
```python
class UnderwritingOverrideRequest(BaseModel):
    override_decision: DecisionEnum  # APPROVED/CONDITIONAL/DECLINED
    reason: str  # Min 20 chars, max 500 chars
    justification: Literal["POLICY_EXCEPTION", "COMPENSATING_FACTORS", "MANAGEMENT_OVERRIDE"]
    compensating_factors: Optional[List[str]] = None  # Required if justification=COMPENSATING_FACTORS
    
    model_config = ConfigDict(min_length=20, max_length=500)
```

**Response Schema:**
```python
class UnderwritingOverrideResponse(BaseModel):
    underwriting_id: UUID
    original_decision: DecisionEnum
    overridden_decision: DecisionEnum
    override_reason: str
    created_at: datetime
    created_by: str  # Hashed admin ID
```

**Error Responses:**
| HTTP | Error Code | Condition |
|------|------------|-----------|
| 404 | `UNDERWRITING_001` | Application not found |
| 403 | `UNDERWRITING_009` | Admin role required |
| 409 | `UNDERWRITING_010` | Cannot override approved application |
| 422 | `UNDERWRITING_002` | Reason too short or justification invalid |

---

## 2. Models & Database

### 2.1 `underwriting_results` Table
```python
class UnderwritingResult(Base):
    __tablename__ = "underwriting_results"
    
    # Primary Key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    
    # Decision & Status
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # APPROVED, CONDITIONAL, DECLINED
    stress_test_passed: Mapped[bool] = mapped_column(nullable=False)
    
    # Ratios (OSFI B-20 compliance)
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ltv_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    
    # Thresholds used (for audit)
    gds_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("39.00"))
    tds_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("44.00"))
    qualifying_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)  # OSFI stress test rate
    
    # CMHC Insurance
    cmhc_required: Mapped[bool] = mapped_column(nullable=False)
    cmhc_premium_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    cmhc_premium_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=True)
    
    # Calculated amounts
    max_mortgage_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monthly_pith_payment: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    
    # Decline reasons (JSON array for flexibility)
    decline_reasons: Mapped[List[Dict]] = mapped_column(JSONB, nullable=True)
    
    # Conditions for conditional approval
    conditions: Mapped[List[Dict]] = mapped_column(JSONB, nullable=True)
    
    # Override tracking
    is_overridden: Mapped[bool] = mapped_column(default=False)
    override_reason: Mapped[str] = mapped_column(Text, nullable=True)
    override_justification: Mapped[str] = mapped_column(String(50), nullable=True)
    overridden_by: Mapped[str] = mapped_column(String(64), nullable=True)  # Hashed user ID
    
    # Audit & Compliance (FINTRAC)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)  # Hashed user ID
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Immutable snapshot of inputs (for audit)
    calculation_inputs: Mapped[Dict] = mapped_column(JSONB, nullable=False)
    
    # Relationships
    application: Mapped["Application"] = relationship(back_populates="underwriting_result")
```

### 2.2 `underwriting_audit_log` Table (FINTRAC compliance)
```python
class UnderwritingAuditLog(Base):
    __tablename__ = "underwriting_audit_log"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    underwriting_id: Mapped[UUID] = mapped_column(ForeignKey("underwriting_results.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # CALCULATE, EVALUATE, OVERRIDE
    action_details: Mapped[Dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)  # Hashed user ID
    
    # FINTRAC: 5-year retention marker
    retention_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now() + text("INTERVAL '5 years'"), 
        nullable=False
    )
```

### 2.3 Indexes
```sql
-- Common query patterns
CREATE INDEX idx_underwriting_results_application_id ON underwriting_results(application_id);
CREATE INDEX idx_underwriting_results_decision ON underwriting_results(decision);
CREATE INDEX idx_underwriting_results_created_at ON underwriting_results(created_at);

-- FINTRAC compliance queries
CREATE INDEX idx_underwriting_audit_log_retention ON underwriting_audit_log(retention_until) 
WHERE retention_until > NOW();

-- OSFI audit queries
CREATE INDEX idx_underwriting_results_ratios ON underwriting_results(gds_ratio, tds_ratio) 
WHERE gds_ratio > 39.00 OR tds_ratio > 44.00;
```

---

## 3. Business Logic

### 3.1 Stress Test Algorithm (OSFI B-20)
```python
def calculate_qualifying_rate(contract_rate: Decimal) -> Decimal:
    """
    OSFI B-20 Guideline: qualifying_rate = max(contract_rate + 2%, 5.25%)
    """
    stress_test_rate = contract_rate + Decimal("2.00")
    floor_rate = Decimal("5.25")
    qualifying_rate = max(stress_test_rate, floor_rate)
    
    # Audit logging
    logger.info(
        "stress_test_calculated",
        contract_rate=str(contract_rate),
        qualifying_rate=str(qualifying_rate),
        calculation_breakdown={
            "stress_test_rate": str(stress_test_rate),
            "floor_rate": str(floor_rate)
        }
    )
    return qualifying_rate
```

### 3.2 GDS/TDS Calculations
```python
def calculate_gds_tds(
    gross_monthly_income: Decimal,
    monthly_pith: Decimal,
    condo_fee: Decimal,
    monthly_debts: Decimal
) -> Tuple[Decimal, Decimal]:
    """
    GDS = (PITH + 50% condo_fee) / Gross Monthly Income
    TDS = (PITH + all debts + 50% condo_fee) / Gross Monthly Income
    """
    condo_fee_adj = condo_fee * Decimal("0.50")
    
    gds = ((monthly_pith + condo_fee_adj) / gross_monthly_income) * Decimal("100")
    tds = ((monthly_pith + monthly_debts + condo_fee_adj) / gross_monthly_income) * Decimal("100")
    
    # Round to 2 decimal places
    gds = gds.quantize(Decimal("0.01"))
    tds = tds.quantize(Decimal("0.01"))
    
    return gds, tds
```

### 3.3 LTV & Down Payment Rules (CMHC)
```python
def calculate_ltv_and_down_payment(
    property_value: Decimal, 
    loan_amount: Decimal
) -> Tuple[Decimal, Decimal, bool]:
    """
    CMHC down payment requirements:
    - ≤$500k: 5% minimum
    - $500k-$1.5M: 5% of first $500k + 10% of remainder
    - >$1.5M: 20% minimum (uninsurable)
    """
    if property_value <= Decimal("500000"):
        min_down = property_value * Decimal("0.05")
    elif property_value <= Decimal("1500000"):
        min_down = Decimal("500000") * Decimal("0.05") + (property_value - Decimal("500000")) * Decimal("0.10")
    else:
        min_down = property_value * Decimal("0.20")
    
    down_payment = property_value - loan_amount
    ltv = (loan_amount / property_value) * Decimal("100")
    ltv = ltv.quantize(Decimal("0.01"))
    
    # Down payment validation
    if down_payment < min_down:
        raise UnderwritingBusinessRuleError(
            f"Insufficient down payment. Required: {min_down}, Provided: {down_payment}"
        )
    
    return ltv, down_payment, down_payment >= min_down
```

### 3.4 CMHC Insurance Premium
```python
def calculate_cmhc_premium(ltv: Decimal, loan_amount: Decimal) -> Tuple[bool, Decimal, Decimal]:
    """
    CMHC premium tiers:
    80.01-85%: 2.80%
    85.01-90%: 3.10%
    90.01-95%: 4.00%
    """
    if ltv <= Decimal("80.00"):
        return False, Decimal("0"), Decimal("0")
    
    if ltv <= Decimal("85.00"):
        rate = Decimal("2.80")
    elif ltv <= Decimal("90.00"):
        rate = Decimal("3.10")
    elif ltv <= Decimal("95.00"):
        rate = Decimal("4.00")
    else:
        raise UnderwritingBusinessRuleError("LTV exceeds insurable limit")
    
    premium = loan_amount * (rate / Decimal("100"))
    premium = premium.quantize(Decimal("0.01"))
    
    return True, premium, rate
```

### 3.5 Decision Engine
```python
def make_underwriting_decision(
    gds: Decimal, tds: Decimal, ltv: Decimal,
    stress_test_passed: bool, credit_score: Optional[int]
) -> Tuple[DecisionEnum, List[str], List[str]]:
    """
    Decision tree:
    - DECLINED if GDS > 44% or TDS > 49% or LTV > 95% or stress_test_passed=False
    - CONDITIONAL if 39% < GDS ≤ 44% or 44% < TDS ≤ 49% or credit_score < 680
    - APPROVED if GDS ≤ 39% and TDS ≤ 44% and LTV ≤ 80% and credit_score ≥ 680
    """
    decline_reasons = []
    conditions = []
    decision = DecisionEnum.APPROVED
    
    # Hard declines (OSFI B-20)
    if not stress_test_passed:
        decline_reasons.append("FAILED_STRESS_TEST")
        decision = DecisionEnum.DECLINED
    
    if gds > Decimal("44.00") or tds > Decimal("49.00"):
        decline_reasons.append("EXCEEDS_MAXIMUM_RATIO")
        decision = DecisionEnum.DECLINED
    
    if ltv > Decimal("95.00"):
        decline_reasons.append("LTV_EXCEEDS_INSURABLE_LIMIT")
        decision = DecisionEnum.DECLINED
    
    # Conditional criteria
    if decision == DecisionEnum.APPROVED:
        if gds > Decimal("39.00"):
            conditions.append("GDS_EXCEEDS_STANDARD_THRESHOLD")
            decision = DecisionEnum.CONDITIONAL
        
        if tds > Decimal("44.00"):
            conditions.append("TDS_EXCEEDS_STANDARD_THRESHOLD")
            decision = DecisionEnum.CONDITIONAL
        
        if credit_score and credit_score < 680:
            conditions.append("CREDIT_SCORE_BELOW_680")
            decision = DecisionEnum.CONDITIONAL
    
    return decision, decline_reasons, conditions
```

### 3.6 State Machine
```
[DRAFT] → [SUBMITTED] → [UNDERWRITING] → [APPROVED/CONDITIONAL/DECLINED]
      ↑              ↓
      └───── [MANUAL_REVIEW] ←── [OVERRIDE_REQUEST]
```

**Transitions:**
- `SUBMITTED → UNDERWRITING`: Triggered by evaluate endpoint
- `UNDERWRITING → APPROVED`: GDS ≤ 39%, TDS ≤ 44%, all validations pass
- `UNDERWRITING → CONDITIONAL`: Ratios within extended thresholds or credit < 680
- `UNDERWRITING → DECLINED`: Ratios exceed maximums or stress test failed
- `UNDERWRITING → MANUAL_REVIEW`: Admin requests manual review
- `MANUAL_REVIEW → OVERRIDE`: Admin override endpoint called

---

## 4. Migrations

### 4.1 New Tables
```sql
-- Table: underwriting_results
CREATE TABLE underwriting_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE RESTRICT,
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('APPROVED', 'CONDITIONAL', 'DECLINED')),
    stress_test_passed BOOLEAN NOT NULL,
    gds_ratio NUMERIC(5,2) NOT NULL,
    tds_ratio NUMERIC(5,2) NOT NULL,
    ltv_ratio NUMERIC(5,2) NOT NULL,
    gds_threshold NUMERIC(5,2) DEFAULT 39.00,
    tds_threshold NUMERIC(5,2) DEFAULT 44.00,
    qualifying_rate NUMERIC(6,3) NOT NULL,
    cmhc_required BOOLEAN NOT NULL,
    cmhc_premium_amount NUMERIC(12,2) DEFAULT 0,
    cmhc_premium_rate NUMERIC(5,2),
    max_mortgage_amount NUMERIC(12,2) NOT NULL,
    monthly_pith_payment NUMERIC(10,2) NOT NULL,
    decline_reasons JSONB,
    conditions JSONB,
    is_overridden BOOLEAN DEFAULT FALSE,
    override_reason TEXT,
    override_justification VARCHAR(50),
    overridden_by VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(64) NOT NULL,
    updated_at TIMESTAMPTZ,
    calculation_inputs JSONB NOT NULL
);

-- Table: underwriting_audit_log
CREATE TABLE underwriting_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    underwriting_id UUID NOT NULL REFERENCES underwriting_results(id),
    action VARCHAR(50) NOT NULL,
    action_details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(64) NOT NULL,
    retention_until TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '5 years'
);
```

### 4.2 Indexes
```sql
-- Performance indexes
CREATE INDEX idx_underwriting_results_app_id ON underwriting_results(application_id);
CREATE INDEX idx_underwriting_results_decision ON underwriting_results(decision);
CREATE INDEX idx_underwriting_results_created ON underwriting_results(created_at);

-- Compliance indexes
CREATE INDEX idx_underwriting_audit_retention ON underwriting_audit_log(retention_until) 
WHERE retention_until > NOW();

-- Risk monitoring indexes
CREATE INDEX idx_underwriting_results_gds_tds ON underwriting_results(gds_ratio, tds_ratio) 
WHERE gds_ratio > 39.00 OR tds_ratio > 44.00;

-- Unique constraint: one active UW result per application
CREATE UNIQUE INDEX uq_underwriting_results_app_id ON underwriting_results(application_id) 
WHERE is_overridden = FALSE;
```

### 4.3 Data Migration
**None required** - new module with no existing data dependencies.

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Stress Test:** All calculations must use `qualifying_rate = max(contract_rate + 2%, 5.25%)`
- **Hard Limits:** GDS ≤ 39%, TDS ≤ 44% for standard approval
- **Audit Trail:** All ratio calculations logged with breakdown in `calculation_inputs`
- **Immutability:** Once evaluated, underwriting results cannot be modified (only overridden)
- **Logging:** Ratio values logged without PII; calculation parameters stored in JSONB

### 5.2 FINTRAC Compliance
- **Transaction Records:** All evaluations create immutable audit log entry
- **Identity Verification:** Application-level verification logged separately; underwriting system references hashed IDs
- **Large Transactions:** Flag applications where loan_amount > CAD $10,000 (all mortgages)
- **Retention:** `underwriting_audit_log.retention_until` enforced at 5 years
- **Reporting:** Decline reasons include "SUSPICIOUS_ACTIVITY" trigger for FINTRAC reporting

### 5.3 PIPEDA Data Handling
- **Encryption at Rest:** 
  - SIN: Encrypted in `applications` table (AES-256), only hashed SIN used in underwriting lookups
  - DOB: Encrypted in `applicants` table, age calculated pre-encryption
  - Income: Stored as Decimal, never in logs
- **Data Minimization:** Underwriting only stores calculated ratios, not raw income sources
- **Access Control:** 
  - `/calculate`: Authenticated lender role
  - `/evaluate`: Underwriter role
  - `/override`: Admin role only
- **Log Sanitization:** All logs filter SIN, DOB, income, banking data

### 5.4 Authentication & Authorization
```python
# Route decorators
@router.post("/calculate", dependencies=[Depends(require_auth), Depends(require_role("lender"))])
@router.post("/applications/{id}/evaluate", dependencies=[Depends(require_auth), Depends(require_role("underwriter"))])
@router.post("/applications/{id}/override", dependencies=[Depends(require_auth), Depends(require_role("admin"))])
```

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy
```python
# In modules/underwriting/exceptions.py
class UnderwritingException(AppException):
    """Base exception for underwriting module"""
    pass

class UnderwritingNotFoundError(UnderwritingException):
    """Resource not found"""
    def __init__(self, resource: str, resource_id: UUID):
        super().__init__(f"{resource} not found: {resource_id}")

class UnderwritingValidationError(UnderwritingException):
    """Input validation failed"""
    def __init__(self, field: str, reason: str):
        super().__init__(f"{field}: {reason}")

class UnderwritingBusinessRuleError(UnderwritingException):
    """Business rule violation"""
    def __init__(self, rule: str, detail: str):
        super().__init__(f"{rule} violated: {detail}")

class UnderwritingOverrideError(UnderwritingException):
    """Override operation failed"""
    pass
```

### 6.2 Error Mapping Table
| Exception Class | HTTP Status | Error Code | Message Pattern | Log Level |
|-----------------|-------------|------------|-----------------|-----------|
| `UnderwritingNotFoundError` | 404 | `UNDERWRITING_001` | "{Resource} not found: {id}" | WARNING |
| `UnderwritingValidationError` | 422 | `UNDERWRITING_002` | "{field}: {reason}" | INFO |
| `UnderwritingBusinessRuleError` | 409 | `UNDERWRITING_003` | "{rule} violated: {detail}" | WARNING |
| `UnderwritingOverrideError` | 400 | `UNDERWRITING_004` | "Override failed: {reason}" | ERROR |
| `SelfEmployedIncomeError` | 422 | `UNDERWRITING_005` | "Self-employed income: {reason}" | INFO |
| `PropertyValueLimitError` | 400 | `UNDERWRITING_006` | "Property value exceeds limit: {value}" | INFO |
| `InsufficientPermissionsError` | 403 | `UNDERWRITING_007` | "Role {role} insufficient" | WARNING |
| `UnauthorizedAccessError` | 403 | `UNDERWRITING_008` | "Access denied to application {id}" | WARNING |
| `AdminRoleRequiredError` | 403 | `UNDERWRITING_009` | "Admin role required" | WARNING |
| `OverrideNotAllowedError` | 409 | `UNDERWRITING_010` | "Override not allowed: {reason}" | WARNING |

### 6.3 Structured Error Response
```json
{
  "detail": "GDS ratio exceeds maximum threshold: 45.20%",
  "error_code": "UNDERWRITING_003",
  "timestamp": "2024-01-15T14:30:00Z",
  "correlation_id": "req-12345",
  "context": {
    "application_id": "uuid-here",
    "gds_ratio": "45.20",
    "threshold": "44.00"
  }
}
```

---

## 7. Missing Details & Warnings

### 7.1 Conditional Approval Criteria
**WARNING:** Detailed conditional criteria not yet defined. Design assumes:
- Ratios 39-44% (GDS) or 44-49% (TDS) trigger conditional status
- Credit score < 680 triggers conditional status
- **RECOMMENDATION:** Create `underwriting_conditions` table to standardize conditions

### 7.2 Decline Reason Templates
**WARNING:** Decline reason taxonomy incomplete. Current design includes:
- `FAILED_STRESS_TEST`
- `EXCEEDS_MAXIMUM_RATIO`
- `LTV_EXCEEDS_INSURABLE_LIMIT`
- `INSUFFICIENT_DOWN_PAYMENT`
- **RECOMMENDATION:** Implement `decline_reasons` reference table with severity levels

### 7.3 Self-Employed Income Rules
**WARNING:** Self-employed income calculation uses simple 2-year average. 
- Does not account for add-backs, expense ratios, or industry risk
- **RECOMMENDATION:** Integrate with `income_verification` module for detailed analysis

### 7.4 Rental Income Treatment
**WARNING:** Rental income inclusion rate fixed at 50%.
- Does not vary by property type or rental agreement type
- **RECOMMENDATION:** Add `rental_income_inclusion_rate` to calculation inputs based on CMHC guidelines

### 7.5 Multi-Property Debt Aggregation
**WARNING:** Design assumes `monthly_non_mortgage_debts` includes all obligations.
- No integration with credit bureau or property portfolio data
- **RECOMMENDATION:** Create `debt_aggregation_service` to pull consolidated debt data

---

## 8. Testing Strategy

### 8.1 Unit Tests (pytest.mark.unit)
- Stress test calculation edge cases (contract_rate = 3.25%, 5.25%)
- GDS/TDS boundary conditions (38.99%, 39.00%, 44.01%)
- CMHC premium tier boundaries (80.01%, 85.01%, 90.01%)
- LTV calculation with various property values

### 8.2 Integration Tests (pytest.mark.integration)
- Full workflow: calculate → evaluate → retrieve result → override
- Role-based access control validation
- Audit log immutability verification
- Concurrent evaluation attempts (race condition handling)

### 8.3 Compliance Tests
- OSFI B-20 ratio limit enforcement
- PIPEDA: Verify SIN/DOB not in logs or responses
- FINTRAC: Verify 5-year retention field populated
- CMHC: Verify premium calculation accuracy within 0.01%

---

## 9. Observability

### 9.1 Structured Logging (structlog)
```python
logger.info(
    "underwriting_evaluation_completed",
    application_id=str(app_id),
    decision=decision,
    gds_ratio=str(gds),
    tds_ratio=str(tds),
    ltv_ratio=str(ltv),
    qualifying_rate=str(qualifying_rate),
    stress_test_passed=stress_test_passed,
    cmhc_required=cmhc_required,
    correlation_id=correlation_id.get()
)
```

### 9.2 Prometheus Metrics
- `underwriting_evaluations_total{decision="approved|conditional|declined"}`
- `underwriting_ratio_violations_total{ratio_type="gds|tds"}`
- `underwriting_cmhc_premiums_sum`
- `underwriting_override_count`

---

## 10. Performance Considerations

- **Query Optimization:** Index on `application_id` for fast result retrieval
- **Caching:** Qualifying rate floor (5.25%) cached in Redis for 24h
- **Async DB:** All calculations use async SQLAlchemy to prevent blocking
- **Connection Pooling:** `pool_size=20`, `max_overflow=50` for high-throughput scenarios
- **Rate Limiting:** `/calculate` endpoint: 100 req/min per user (prevents abuse)

---

**Design Approval:** This plan must be reviewed by compliance team before implementation.