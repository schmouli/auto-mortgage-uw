# Design: Decision Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Decision Service Module Design Plan

**File:** `docs/design/decision-service.md`

---

## 1. Endpoints

### 1.1 POST /api/v1/decision/evaluate
Run deterministic underwriting decision engine against submitted application data.

**Authentication:** Authenticated (JWT, `underwriter` role)

**Request Schema (`schemas.DecisionEvaluationRequest`):**
```python
{
    "application_id": UUID,  # Required
    "borrower_profile": {
        "gross_annual_income": Decimal,  # Required, > 0
        "monthly_debt_obligations": Decimal,  # Required, ≥ 0
        "employment_type": Enum["salaried", "self_employed", "contract"],  # Required
        "credit_score": int,  # Optional, 300-900
    },
    "property_details": {
        "property_value": Decimal,  # Required, > 0
        "annual_property_tax": Decimal,  # Required, ≥ 0
        "monthly_heating_cost": Decimal,  # Required, ≥ 0
    },
    "loan_details": {
        "mortgage_amount": Decimal,  # Required, > 0
        "contract_interest_rate": Decimal,  # Required, > 0
        "amortization_years": int,  # Required, 5-30
        "loan_purpose": Enum["purchase", "refinance", "renewal"],  # Required
    },
    "requesting_user_id": UUID,  # Required, for audit trail
}
```

**Response Schema (`schemas.DecisionEvaluationResponse`):**
```python
{
    "application_id": UUID,
    "decision": Enum["approved", "declined", "exception"],
    "confidence_score": Decimal,  # 0.00 to 1.00, 2 decimal places
    "ratios": {
        "gds": Decimal,  # 2 decimal places
        "tds": Decimal,  # 2 decimal places
        "ltv": Decimal,  # 2 decimal places
    },
    "cmhc_required": bool,
    "stress_test_rate": Decimal,  # 2 decimal places
    "policy_flags": List[str],  # e.g., ["high_ltv", "self_employed_income"]
    "exceptions": List[Dict[str, Any]],  # Rule violations
    "audit_trail": {
        "rules_evaluated": int,  # Count of rules processed
        "timestamp": datetime,
        "model_version": str,  # Semantic version of policy rule set
    },
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 422 | `DECISION_001` | `gross_annual_income` ≤ 0 or missing required fields |
| 422 | `DECISION_002` | `mortgage_amount` > `property_value` (negative equity) |
| 422 | `DECISION_003` | `amortization_years` outside 5-30 range |
| 409 | `DECISION_004` | Decision already exists for `application_id` |
| 403 | `AUTH_001` | Insufficient permissions |

---

### 1.2 GET /api/v1/decision/{application_id}
Retrieve cached decision record by application ID.

**Authentication:** Authenticated (JWT, `underwriter` or `admin` role)

**Path Parameter:** `application_id: UUID`

**Response Schema:** Same as `DecisionEvaluationResponse`

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `DECISION_005` | Decision record not found |
| 403 | `AUTH_001` | Insufficient permissions |

---

### 1.3 GET /api/v1/decision/{application_id}/audit
Retrieve immutable audit trail for regulatory examination (FINTRAC 5-year retention).

**Authentication:** Authenticated (JWT, `admin` or `compliance` role)

**Path Parameter:** `application_id: UUID`

**Response Schema (`schemas.DecisionAuditResponse`):**
```python
{
    "application_id": UUID,
    "decision_snapshot": Dict[str, Any],  # Full decision output
    "rule_evaluations": List[Dict[str, Any]],  # Each rule evaluated
    "calculation_breakdown": {
        "gds": {
            "pith": Decimal,
            "gross_monthly_income": Decimal,
            "formula": str,
        },
        "tds": {
            "pith_plus_debts": Decimal,
            "gross_monthly_income": Decimal,
            "formula": str,
        },
        "ltv": {
            "mortgage_amount": Decimal,
            "property_value": Decimal,
            "formula": str,
        },
        "stress_test": {
            "contract_rate": Decimal,
            "qualifying_rate": Decimal,
            "floor_rate": Decimal,
            "formula": str,
        },
    },
    "created_at": datetime,
    "created_by": UUID,
    "model_version": str,
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `DECISION_006` | Audit trail not found |
| 403 | `AUTH_002` | Compliance role required |

---

## 2. Models & Database

### 2.1 `decision_records` Table
**Purpose:** Store final underwriting decision (immutable after creation)

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | |
| `application_id` | UUID | UNIQUE, NOT NULL | `idx_application_id` |
| `decision` | VARCHAR(10) | CHECK IN ('approved', 'declined', 'exception') | |
| `confidence_score` | DECIMAL(5,2) | NOT NULL | |
| `gds_ratio` | DECIMAL(5,2) | NOT NULL | `idx_gds_high` |
| `tds_ratio` | DECIMAL(5,2) | NOT NULL | `idx_tds_high` |
| `ltv_ratio` | DECIMAL(5,2) | NOT NULL | `idx_ltv_high` |
| `cmhc_required` | BOOLEAN | NOT NULL | |
| `stress_test_rate` | DECIMAL(5,2) | NOT NULL | |
| `policy_flags` | JSONB | NOT NULL, default [] | GIN index |
| `exceptions` | JSONB | NOT NULL, default [] | GIN index |
| `model_version` | VARCHAR(20) | NOT NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() | `idx_created_at` |
| `created_by` | UUID | NOT NULL | `idx_created_by` |

**Relationships:** None (denormalized for audit immutability)

---

### 2.2 `decision_audit_logs` Table
**Purpose:** FINTRAC-compliant immutable audit trail (5-year retention)

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | |
| `application_id` | UUID | NOT NULL | `idx_application_audit` |
| `decision_record_id` | UUID | FOREIGN KEY → decision_records.id | |
| `calculation_breakdown` | JSONB | NOT NULL (encrypted) | |
| `rule_evaluations` | JSONB | NOT NULL (encrypted) | |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() | `idx_audit_created` |
| `created_by` | UUID | NOT NULL | |

**Note:** `calculation_breakdown` and `rule_evaluations` encrypted with AES-256 to protect income and debt values (PIPEDA). Never logged to structlog.

---

### 2.3 `policy_rules` Table
**Purpose:** Versioned policy rule definitions for deterministic evaluation

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | |
| `rule_code` | VARCHAR(50) | UNIQUE, NOT NULL | `idx_rule_code` |
| `description` | TEXT | NOT NULL | |
| `rule_type` | VARCHAR(20) | CHECK IN ('gds', 'tds', 'ltv', 'credit', 'income', 'stress_test') | |
| `operator` | VARCHAR(10) | CHECK IN ('>', '<', '>=', '<=', '==', '!=') | |
| `threshold_value` | DECIMAL(10,2) | NOT NULL | |
| `exception_severity` | VARCHAR(10) | CHECK IN ('low', 'medium', 'high', 'critical') | |
| `is_active` | BOOLEAN | NOT NULL, default True | `idx_active_rules` |
| `model_version` | VARCHAR(20) | NOT NULL | `idx_version_rules` |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default now() | |

**Example Rows:**
- `rule_code: "OSFI_GDS_MAX"`, `threshold_value: 39.00`, `exception_severity: "critical"`
- `rule_code: "OSFI_TDS_MAX"`, `threshold_value: 44.00`, `exception_severity: "critical"`
- `rule_code: "CMHC_LTV_INSURANCE_THRESHOLD"`, `threshold_value: 80.00`, `exception_severity: "medium"`

---

### 2.4 Indexes for Query Performance
```sql
-- Common compliance queries
CREATE INDEX idx_decision_created_5year ON decision_records (created_at) 
WHERE created_at >= NOW() - INTERVAL '5 years';

-- High-risk decision review
CREATE INDEX idx_exceptions_gin ON decision_audit_logs USING GIN (exceptions);

-- Model version drift detection
CREATE INDEX idx_model_version ON decision_records (model_version, created_at);
```

---

## 3. Business Logic

### 3.1 Decision Engine Algorithm (`services.DecisionEngine`)
```python
async def evaluate(application_data: DecisionEvaluationRequest) -> DecisionEvaluationResponse:
    # 1. Input validation (strict bounds checking)
    validate_financial_bounds(application_data)
    
    # 2. LTV Calculation & CMHC Insurance Logic (CMHC requirement)
    ltv_ratio = calculate_ltv(
        loan_amount=application_data.loan_details.mortgage_amount,
        property_value=application_data.property_details.property_value
    )
    cmhc_required = ltv_ratio > Decimal('80.00')
    
    # 3. Stress Test Rate (OSFI B-20 mandatory)
    contract_rate = application_data.loan_details.contract_interest_rate
    floor_rate = Decimal('5.25')
    stress_test_rate = max(contract_rate + Decimal('2.00'), floor_rate)
    
    # 4. Monthly Payment Calculations
    monthly_payment = calculate_pmt(
        principal=application_data.loan_details.mortgage_amount,
        rate=stress_test_rate,
        amortization=application_data.loan_details.amortization_years
    )
    
    # 5. PITH Calculation
    monthly_tax = application_data.property_details.annual_property_tax / Decimal('12')
    pith = monthly_payment + monthly_tax + application_data.property_details.monthly_heating_cost
    
    # 6. Gross Monthly Income (self-employed rule: 2-year average)
    gross_monthly_income = calculate_gross_monthly_income(
        annual_income=application_data.borrower_profile.gross_annual_income,
        employment_type=application_data.borrower_profile.employment_type
    )
    
    # 7. Ratio Calculations with Audit Logging
    gds_ratio = (pith / gross_monthly_income) * Decimal('100')
    tds_ratio = ((pith + application_data.borrower_profile.monthly_debt_obligations) / gross_monthly_income) * Decimal('100')
    
    # 8. Rule Evaluation (deterministic, ordered by severity)
    rule_violations = evaluate_all_rules(
        gds_ratio=gds_ratio,
        tds_ratio=tds_ratio,
        ltv_ratio=ltv_ratio,
        credit_score=application_data.borrower_profile.credit_score,
        cmhc_required=cmhc_required
    )
    
    # 9. Decision Determination with Prioritization
    decision, confidence_score, policy_flags = determine_decision_outcome(rule_violations)
    
    # 10. Immutable Audit Trail Creation (FINTRAC)
    await create_audit_log(
        application_id=application_data.application_id,
        calculation_breakdown=build_calculation_breakdown(...),
        rule_evaluations=rule_violations,
        created_by=application_data.requesting_user_id
    )
    
    return DecisionEvaluationResponse(...)
```

---

### 3.2 Self-Employed Income Calculation Rules
```python
def calculate_gross_monthly_income(annual_income: Decimal, employment_type: str) -> Decimal:
    if employment_type == "self_employed":
        # Require 2-year NOA average with 15% gross-up add-back
        # This is a simplified rule - production would fetch historical data
        return (annual_income * Decimal('1.15')) / Decimal('12')
    return annual_income / Decimal('12')
```

---

### 3.3 Decision Outcome Determination Logic
```python
def determine_decision_outcome(violations: List[RuleViolation]) -> Tuple[str, Decimal, List[str]]:
    """
    Prioritization hierarchy:
    1. Critical violations (OSFI GDS/TDS breach) → declined
    2. High severity + multiple medium → exception (manual review)
    3. Medium severity only → conditional approval
    4. Low severity → approved with flags
    """
    critical = [v for v in violations if v.severity == "critical"]
    high = [v for v in violations if v.severity == "high"]
    medium = [v for v in violations if v.severity == "medium"]
    
    if critical:
        return "declined", Decimal("0.00"), [v.code for v in critical]
    
    if high or len(medium) >= 2:
        # Exception workflow: route to senior underwriter
        return "exception", Decimal("0.75"), [v.code for v in (high + medium)]
    
    if medium:
        # Conditional approval: e.g., require CMHC insurance proof
        return "approved", Decimal("0.85"), ["conditional_approval"] + [v.code for v in medium]
    
    return "approved", Decimal("0.98"), []
```

---

### 3.4 Confidence Score Formula
```python
confidence_score = Decimal('1.00') - (severity_weight * violation_count * Decimal('0.05'))

Where severity_weight:
- critical: 1.0
- high: 0.75
- medium: 0.5
- low: 0.25

Capped at 0.00 minimum.
```

---

## 4. Migrations

### 4.1 New Tables
```sql
-- 001_create_decision_service_tables.sql
CREATE TABLE decision_records (...);
CREATE TABLE decision_audit_logs (...);
CREATE TABLE policy_rules (...);
```

### 4.2 Seed Data (CMHC & OSFI Rules)
```sql
INSERT INTO policy_rules (rule_code, description, rule_type, operator, threshold_value, exception_severity, model_version) VALUES
('OSFI_GDS_MAX', 'Gross Debt Service ≤ 39%', 'gds', '<=', 39.00, 'critical', '1.0.0'),
('OSFI_TDS_MAX', 'Total Debt Service ≤ 44%', 'tds', '<=', 44.00, 'critical', '1.0.0'),
('CMHC_LTV_INSURANCE_80', 'LTV > 80% requires insurance', 'ltv', '>', 80.00, 'medium', '1.0.0'),
('CMHC_LTV_MAX_INSURED', 'LTV cannot exceed 95% for insured', 'ltv', '<=', 95.00, 'critical', '1.0.0'),
('CREDIT_SCORE_MIN', 'Minimum credit score 600', 'credit', '>=', 600.00, 'high', '1.0.0');
```

### 4.3 Indexes
```sql
CREATE INDEX idx_decision_application ON decision_records(application_id);
CREATE INDEX idx_audit_5year ON decision_audit_logs(created_at) 
WHERE created_at >= NOW() - INTERVAL '5 years';
CREATE INDEX idx_policy_rules_active ON policy_rules(is_active, model_version);
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Implementation
- **Stress Test:** Hardcoded floor rate 5.25% enforced in `calculate_stress_test_rate()`
- **GDS/TDS Limits:** Critical rule violations in `policy_rules` table with severity="critical"
- **Auditability:** All ratio calculations serialized to `calculation_breakdown` JSONB and encrypted
- **Logging:** Calculation formulas logged to `decision_audit_logs` table only; never to structlog

### 5.2 FINTRAC Compliance
- **Immutable Records:** `decision_audit_logs` table has no UPDATE/DELETE endpoints; INSERT only
- **5-Year Retention:** PostgreSQL partition policy on `created_at` column; automated archive to cold storage after 5 years
- **Transaction Flagging:** Applications > CAD $10,000 automatically flagged in `policy_flags` as "large_transaction"
- **Audit Trail:** `created_by` field captures user ID for every decision; no anonymous evaluations

### 5.3 CMHC Insurance Logic
```python
def calculate_cmhc_premium(ltv_ratio: Decimal) -> Decimal:
    if Decimal('80.01') <= ltv_ratio <= Decimal('85.00'):
        return Decimal('2.80')
    elif Decimal('85.01') <= ltv_ratio <= Decimal('90.00'):
        return Decimal('3.10')
    elif Decimal('90.01') <= ltv_ratio <= Decimal('95.00'):
        return Decimal('4.00')
    return Decimal('0.00')
```

### 5.4 PIPEDA Data Handling
- **Encryption:** `calculation_breakdown` and `rule_evaluations` JSONB fields encrypted with AES-256-GCM via `common.security.encrypt_pii()`
- **No Logging:** Income, debt, or SIN values never appear in structlog logs; only UUIDs and ratios
- **Data Minimization:** Request schema excludes SIN/DOB; only receives pre-extracted financial aggregates
- **Lookup Hashes:** If SIN-based lookup required, use SHA256 hash only

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy (`exceptions.py`)
```python
class DecisionServiceException(AppException):
    """Base exception for decision service module"""
    pass

class DecisionValidationError(DecisionServiceException):
    """Input validation failed (422)"""
    error_code = "DECISION_001"

class DecisionConflictError(DecisionServiceException):
    """Decision already exists (409)"""
    error_code = "DECISION_004"

class DecisionNotFoundError(DecisionServiceException):
    """Decision or audit record not found (404)"""
    error_code = "DECISION_005"
```

### 6.2 Error Mapping Table
| Exception Class | HTTP Status | Error Code | Message Pattern | Log Level |
|-----------------|-------------|------------|-----------------|-----------|
| `DecisionValidationError` | 422 | DECISION_001 | "Field validation failed: {field}" | WARNING |
| `DecisionValidationError` | 422 | DECISION_002 | "Loan amount exceeds property value" | WARNING |
| `DecisionValidationError` | 422 | DECISION_003 | "Amortization must be 5-30 years" | WARNING |
| `DecisionConflictError` | 409 | DECISION_004 | "Decision for application {id} already exists" | INFO |
| `DecisionNotFoundError` | 404 | DECISION_005 | "Decision record not found" | INFO |
| `DecisionNotFoundError` | 404 | DECISION_006 | "Audit trail not found" | INFO |
| `AppException` (base) | 500 | DECISION_999 | "Internal decision engine error" | ERROR |

---

### 6.3 Structured Error Response Format
All errors return:
```json
{
    "detail": "Human-readable message",
    "error_code": "DECISION_XXX",
    "timestamp": "2024-01-15T14:30:00Z",
    "correlation_id": "req-12345678-abcd-ef12-3456-7890abcdef12"
}
```

---

## 7. Conditional Approval & Exception Workflow (Gap Coverage)

### 7.1 Conditional Approval Criteria
Decision = "approved" with `policy_flags` containing "conditional_approval" when:
- LTV 80.01-85% + GDS 35-39% (medium risk)
- Self-employed income verified via 2-year NOA (flag: "income_verified")
- Credit score 600-650 (subprime but acceptable with insurance)

**Conditions stored in:** `decision_records.exceptions` JSONB as:
```json
[
    {
        "type": "conditional",
        "condition": "provide_cmhc_insurance_certificate",
        "deadline_days": 30
    }
]
```

### 7.2 Exception Handling Workflow
Decision = "exception" triggers:
1. Async event published to `underwriting.exceptions` queue
2. Senior underwriter task created in workflow service
3. Application routed to manual review queue
4. Confidence score capped at 0.75 to indicate uncertainty

### 7.3 Decline Reason Prioritization
When multiple critical violations exist, return only the highest priority:
1. `OSFI_TDS_MAX` (TDS > 44%) - **Priority 1**
2. `OSFI_GDS_MAX` (GDS > 39%) - **Priority 2**
3. `CMHC_LTV_MAX_INSURED` (LTV > 95%) - **Priority 3**
4. `CREDIT_SCORE_MIN` (Credit < 600) - **Priority 4**

---

## 8. Observability & Monitoring

### 8.1 Prometheus Metrics
- `decision_requests_total` (counter, labels: decision_type, model_version)
- `decision_evaluation_duration_seconds` (histogram)
- `decision_exceptions_total` (counter, labels: severity)
- `cmhc_insurance_required_total` (counter)

### 8.2 OpenTelemetry Tracing
- Span per rule evaluation
- Span for encryption/decryption operations
- Span for audit log persistence

---

## 9. Testing Strategy

### 9.1 Unit Tests (`tests/unit/test_decision_service.py`)
- Stress test calculation edge cases (contract_rate = 3.25%, 5.25%)
- GDS/TDS boundary values (38.9%, 39.0%, 39.1%)
- LTV premium tier boundaries (80.01%, 85.00%, 85.01%)
- Confidence score formula verification

### 9.2 Integration Tests (`tests/integration/test_decision_service_integration.py`)
- Full request/response cycle with PostgreSQL
- Audit log immutability verification
- Concurrent decision requests for same application_id (conflict handling)
- Role-based access control for audit endpoint

---

## 10. Deployment Notes

- **Model Versioning:** Policy rules deployed via Alembic migration; rollback requires new migration (never modify existing)
- **Zero-Downtime:** Decision engine is stateless; deploy new version with updated `model_version` in rules table
- **Secret Rotation:** AES-256 encryption key stored in `common.config.Config.DECRYPTION_KEY`; rotation triggers re-encryption job
- **Compliance Export:** Monthly cron job exports `decision_audit_logs` to FINTRAC reporting format (XML) with digital signature

---