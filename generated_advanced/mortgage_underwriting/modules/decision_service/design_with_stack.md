# Design: Decision Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Decision Service Module Design Plan

## docs/design/decision-service.md

---

### 1. Endpoints

#### `POST /api/v1/decision/evaluate`
**Purpose**: Execute deterministic underwriting decision engine against a submitted mortgage application.

**Authentication**: Authenticated user (JWT required). `created_by` populated from `sub` claim.

**Request Body Schema**:
```python
class DecisionEvaluateRequest(BaseModel):
    application_id: UUID
    borrower_data: BorrowerData
    property_data: PropertyData
    loan_data: LoanData
    existing_debts: List[DebtItem] = []
    
class BorrowerData(BaseModel):
    gross_annual_income: Decimal  # Before-tax income, self-employed handled via 2-year avg
    monthly_non_housing_debt: Decimal  # Sum of credit cards, loans, alimony
    employment_type: Literal["salaried", "self_employed", "contractor"]
    sin_hash: str  # SHA256 hash for PIPEDA compliance, never plaintext
    
class PropertyData(BaseModel):
    property_value: Decimal
    property_type: Literal["single_family", "condo", "rental"]
    
class LoanData(BaseModel):
    mortgage_amount: Decimal
    contract_rate: Decimal  # Annual interest rate (e.g., 5.25)
    amortization_years: int  # 25 or 30 years
    payment_frequency: Literal["monthly", "bi_weekly", "accelerated_bi_weekly"]
    
class DebtItem(BaseModel):
    monthly_payment: Decimal
    debt_type: Literal["credit_card", "car_loan", "student_loan", "alimony"]
```

**Response Schema**:
```python
class DecisionEvaluateResponse(BaseModel):
    application_id: UUID
    decision: Literal["approved", "declined", "exception", "conditional"]
    confidence_score: Decimal  # 0.00 to 1.00
    ratios: RatioBreakdown
    cmhc_required: bool
    stress_test_rate: Decimal
    policy_flags: List[str]  # e.g., ["ltv_threshold_exceeded", "gds_marginal"]
    exceptions: List[ExceptionItem]
    audit_trail: AuditSummary
    
class RatioBreakdown(BaseModel):
    gds: Decimal  # Calculated GDS ratio
    tds: Decimal  # Calculated TDS ratio
    ltv: Decimal  # Calculated LTV ratio
    gross_monthly_income: Decimal
    pith: Decimal  # Principal + Interest + Taxes + Heat
    
class ExceptionItem(BaseModel):
    rule_id: str
    severity: Literal["error", "warning"]
    message: str
    decline_reason_code: Optional[str]  # Populated if decision == "declined"
    
class AuditSummary(BaseModel):
    rules_evaluated: int
    timestamp: datetime
    model_version: str  # Semantic versioning of rule engine
    evaluated_by: str  # User UUID from JWT
```

**Error Responses**:
| HTTP Status | Error Code | Detail | Trigger |
|-------------|------------|--------|---------|
| 400 | DECISION_001 | "Invalid application_id format" | Malformed UUID |
| 422 | DECISION_002 | "gross_annual_income: must be positive" | Pydantic validation failure |
| 422 | DECISION_003 | "LTV exceeds 95% maximum for insured mortgages" | Business rule violation on input |
| 409 | DECISION_004 | "Decision already exists for application" | Duplicate evaluation attempt |
| 500 | DECISION_005 | "Policy rule engine internal error" | Unhandled exception during evaluation |

---

#### `GET /api/v1/decision/{application_id}`
**Purpose**: Retrieve finalized decision record by application ID.

**Authentication**: Authenticated user. Authorization check: user must own application or have `underwriter` role.

**Path Parameter**: `application_id: UUID`

**Response Schema**: `DecisionEvaluateResponse` (same as above)

**Error Responses**:
| HTTP Status | Error Code | Detail | Trigger |
|-------------|------------|--------|---------|
| 404 | DECISION_011 | "Decision not found" | No record for application_id |
| 403 | DECISION_012 | "Access denied to decision record" | User lacks authorization |

---

#### `GET /api/v1/decision/{application_id}/audit`
**Purpose**: Retrieve full immutable audit trail for regulatory examination (FINTRAC 5-year retention).

**Authentication**: Authenticated user with `audit_viewer` or `underwriter` role.

**Path Parameter**: `application_id: UUID`

**Response Schema**:
```python
class DecisionAuditTrailResponse(BaseModel):
    application_id: UUID
    decision_snapshot: DecisionEvaluateResponse
    full_audit_log: List[RuleEvaluationLog]
    created_at: datetime
    created_by: str
    
class RuleEvaluationLog(BaseModel):
    log_id: UUID
    rule_id: str
    rule_name: str
    evaluated_at: datetime
    input_context: Dict[str, Any]  # Ratios, income, etc. (no PII)
    result: bool
    triggered_flags: List[str]
    decline_reason: Optional[str]
```

**Error Responses**:
| HTTP Status | Error Code | Detail | Trigger |
|-------------|------------|--------|---------|
| 404 | DECISION_021 | "Audit trail not found" | No audit log for application_id |
| 403 | DECISION_022 | "Audit access requires elevated permissions" | Missing required role |

---

### 2. Models & Database

#### `decision_records` Table
```sql
CREATE TABLE decision_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL UNIQUE,
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('approved', 'declined', 'exception', 'conditional')),
    confidence_score DECIMAL(5,4) NOT NULL,
    gds_ratio DECIMAL(5,2) NOT NULL,
    tds_ratio DECIMAL(5,2) NOT NULL,
    ltv_ratio DECIMAL(5,2) NOT NULL,
    cmhc_required BOOLEAN NOT NULL,
    stress_test_rate DECIMAL(5,2) NOT NULL,
    policy_flags TEXT[],  -- Array of flag identifiers
    gross_monthly_income DECIMAL(12,2) NOT NULL,
    pith DECIMAL(12,2) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    created_by VARCHAR(255) NOT NULL,  -- User UUID from JWT
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX idx_decision_app_id ON decision_records(application_id);
CREATE INDEX idx_decision_created_by ON decision_records(created_by);
CREATE INDEX idx_decision_timestamp ON decision_records(created_at DESC);
```

#### `decision_audit_logs` Table (FINTRAC Immutable)
```sql
CREATE TABLE decision_audit_logs (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES decision_records(id) ON DELETE CASCADE,
    rule_id VARCHAR(50) NOT NULL,
    rule_name VARCHAR(255) NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    input_context JSONB NOT NULL,  -- Serialized calculation inputs (no PII)
    result BOOLEAN NOT NULL,
    triggered_flags TEXT[],
    decline_reason VARCHAR(100),  -- Populated only if rule triggers decline
    created_by VARCHAR(255) NOT NULL
);

-- Composite index for audit retrieval performance
CREATE INDEX idx_audit_decision_id ON decision_audit_logs(decision_id, evaluated_at DESC);
CREATE INDEX idx_audit_rule_id ON decision_audit_logs(rule_id);
```

#### `policy_rules` Table (Versioned Ruleset)
```sql
CREATE TABLE policy_rules (
    rule_id VARCHAR(50) PRIMARY KEY,
    rule_name VARCHAR(255) NOT NULL,
    rule_category VARCHAR(50) NOT NULL,  -- 'gds', 'tds', 'ltv', 'stress_test', 'cmhc'
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('error', 'warning')),
    decline_reason_code VARCHAR(20),  -- e.g., 'GDS_EXCEEDED', 'LTV_UNINSURABLE'
    evaluation_logic JSONB NOT NULL,  -- Stores threshold values and conditions
    version INT NOT NULL DEFAULT 1,
    effective_from TIMESTAMPTZ NOT NULL,
    effective_to TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for active rule lookup
CREATE INDEX idx_policy_rules_active ON policy_rules(enabled, effective_from, effective_to) 
WHERE enabled = TRUE AND effective_to IS NULL;
```

#### `decision_exceptions` Table
```sql
CREATE TABLE decision_exceptions (
    exception_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES decision_records(id) ON DELETE CASCADE,
    rule_id VARCHAR(50) NOT NULL,
    exception_type VARCHAR(50) NOT NULL,  -- 'calculation_error', 'missing_data', 'policy_conflict'
    exception_message TEXT NOT NULL,
    handled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_exceptions_decision_id ON decision_exceptions(decision_id);
```

---

### 3. Business Logic

#### Core Calculation Algorithms

**Stress Test Rate**:
```python
def calculate_qualifying_rate(contract_rate: Decimal) -> Decimal:
    """OSFI B-20: Qualifying rate = max(contract_rate + 2%, 5.25%)"""
    stress_threshold = Decimal("5.25")
    buffered_rate = contract_rate + Decimal("2.00")
    return max(buffered_rate, stress_threshold)
```

**GDS Calculation**:
```python
def calculate_gds(pith: Decimal, gross_monthly_income: Decimal) -> Decimal:
    """
    GDS = (PITH / Gross Monthly Income) × 100
    PITH = Principal + Interest (at stress test rate) + Property Tax + Heat
    """
    if gross_monthly_income == 0:
        raise DecisionBusinessRuleError("Income cannot be zero for ratio calculation")
    return (pith / gross_monthly_income) * Decimal("100")
```
**Threshold**: GDS ≤ 39% (hard limit)

**TDS Calculation**:
```python
def calculate_tds(pith: Decimal, total_monthly_debts: Decimal, gross_monthly_income: Decimal) -> Decimal:
    """
    TDS = (PITH + All Monthly Debts) / Gross Monthly Income × 100
    """
    return ((pith + total_monthly_debts) / gross_monthly_income) * Decimal("100")
```
**Threshold**: TDS ≤ 44% (hard limit)

**LTV Calculation**:
```python
def calculate_ltv(mortgage_amount: Decimal, property_value: Decimal) -> Decimal:
    """LTV = (Mortgage Amount / Property Value) × 100"""
    if property_value == 0:
        raise DecisionValidationError("Property value cannot be zero")
    return (mortgage_amount / property_value) * Decimal("100")
```
**Thresholds**: 
- Insured: LTV ≤ 95%
- Conventional: LTV ≤ 80%

**Self-Employed Income Calculation**:
```python
def calculate_self_employed_income(year_1_income: Decimal, year_2_income: Decimal) -> Decimal:
    """
    2-year average with 15% gross-up for business expenses
    CMHC guideline: (Year1 + Year2) / 2 × 1.15
    """
    two_year_avg = (year_1_income + year_2_income) / Decimal("2")
    return two_year_avg * Decimal("1.15")
```

#### Decision Matrix & State Transitions

```python
DECISION_FLOW = {
    "approved": {
        "conditions": [
            "gds <= 39",
            "tds <= 44", 
            "ltv <= 80 OR (ltv <= 95 AND cmhc_required = True)",
            "stress_test_rate >= qualifying_rate",
            "no_critical_policy_flags"
        ],
        "confidence_score": "1.00"
    },
    "conditional": {
        "conditions": [
            "gds in (37-39) OR tds in (42-44)",  # Marginal ratios
            "ltv in (75-80) AND cmhc_required = False",  # Near-insurable threshold
            "non-traditional_downpayment",  # Gifted funds > 50%
            "thin_credit_file"  # < 2 trade lines
        ],
        "confidence_score": "0.75-0.89",
        "requirements": ["additional_documentation", "exception_approval"]
    },
    "exception": {
        "conditions": [
            "calculation_error",
            "missing_required_field",
            "policy_rule_conflict",
            "manual_review_triggered"
        ],
        "confidence_score": "0.00",
        "workflow": "escalate_to_underwriter"
    },
    "declined": {
        "priority_order": [  # Decline reason precedence
            "LTV_UNINSURABLE",  # LTV > 95%
            "GDS_EXCEEDED",     # GDS > 39%
            "TDS_EXCEEDED",     # TDS > 44%
            "INSUFFICIENT_INCOME_VERIFICATION",
            "PROPERTY_TYPE_INELIGIBLE"
        ],
        "confidence_score": "1.00"
    }
}
```

#### Decline Reason Prioritization
When multiple rules fail, the system selects the highest-priority decline reason:
1. **LTV_UNINSURABLE** (LTV > 95%) - immediate decline, no exceptions
2. **GDS_EXCEEDED** - if GDS > 39%
3. **TDS_EXCEEDED** - if TDS > 44% and GDS ≤ 39%
4. **INSUFFICIENT_INCOME_VERIFICATION** - self-employed without 2-year NOA
5. **PROPERTY_TYPE_INELIGIBLE** - rental properties with LTV > 80%

#### Conditional Approval Criteria
Triggers `decision = "conditional"` when:
- GDS 37-39% or TDS 42-44% (marginal but within limits)
- LTV 75.01-80% (conventional but near CMHC threshold)
- Non-traditional downpayment sources > 50% of total
- Credit history < 2 years but score > 680
**Conditions**: Require additional docs, co-signer, or rate premium (+0.25%)

#### Exception Handling Workflow
```python
async def evaluate_with_exception_handling(application_data):
    try:
        return await run_rule_engine(application_data)
    except MissingDataError as e:
        await log_exception(decision_id, e, "missing_data")
        return DecisionResult(decision="exception", confidence_score=0, exceptions=[e])
    except CalculationError as e:
        await log_exception(decision_id, e, "calculation_error")
        return DecisionResult(decision="exception", confidence_score=0, exceptions=[e])
    except PolicyConflictError as e:
        await log_exception(decision_id, e, "policy_conflict")
        escalate_to_underwriter(application_data)
        return DecisionResult(decision="exception", confidence_score=0, exceptions=[e])
```

---

### 4. Migrations

#### Alembic Revision: `create_decision_service_tables`

**New Tables**:
- `decision_records`
- `decision_audit_logs`
- `policy_rules`
- `decision_exceptions`

**Indexes**:
- Composite index on `decision_records(application_id, created_at)`
- Partial index on `policy_rules` for active rules
- GIN index on `decision_audit_logs.input_context` for JSONB queries

**Data Migration**:
- Seed `policy_rules` table with OSFI B-20 baseline rules:
  ```sql
  INSERT INTO policy_rules (rule_id, rule_name, rule_category, severity, decline_reason_code, evaluation_logic) VALUES
  ('GDS_LIMIT', 'GDS Ratio Maximum', 'gds', 'error', 'GDS_EXCEEDED', '{"threshold": 39.0}'),
  ('TDS_LIMIT', 'TDS Ratio Maximum', 'tds', 'error', 'TDS_EXCEEDED', '{"threshold": 44.0}'),
  ('LTV_INSURED_MAX', 'LTV Maximum Insured', 'ltv', 'error', 'LTV_UNINSURABLE', '{"threshold": 95.0}'),
  ('STRESS_TEST_MIN', 'Stress Test Floor Rate', 'stress_test', 'error', None, '{"floor_rate": 5.25}');
  ```

**No modifications to existing migrations** - all changes in new revision.

---

### 5. Security & Compliance

#### OSFI B-20 Requirements
- **Stress Test Enforcement**: All calculations must use `qualifying_rate = max(contract_rate + 2%, 5.25%)`. Log the `contract_rate`, `buffered_rate`, and final `qualifying_rate` in `decision_audit_logs.input_context`.
- **Hard Limits**: GDS ≤ 39%, TDS ≤ 44% enforced at rule engine level. Any breach results in automatic decline unless `exception` workflow triggered.
- **Auditability**: Every ratio calculation stored with full breakdown in `decision_audit_logs`. Immutable logs retained for 7 years (exceeds FINTRAC 5-year requirement).

#### FINTRAC Compliance
- **Immutable Audit Trail**: `decision_audit_logs` table has no UPDATE/DELETE endpoints. `created_at` timestamp is immutable.
- **Transaction Logging**: All decision evaluations logged with `created_by` user UUID. Records > CAD $10,000 flagged via `policy_flags` array.
- **5-Year Retention**: Database retention policy set on `decision_audit_logs` table: `RETENTION POLICY decision_logs_policy (LOG_AGE > 5 YEARS)`.

#### CMHC Insurance Logic
```python
def determine_cmhc_requirement(ltv: Decimal) -> Tuple[bool, Optional[Decimal]]:
    """
    Returns (insurance_required, premium_rate)
    Premium tiers: 80.01-85% = 2.80%, 85.01-90% = 3.10%, 90.01-95% = 4.00%
    """
    if ltv <= Decimal("80.00"):
        return False, None
    elif Decimal("80.01") <= ltv <= Decimal("85.00"):
        return True, Decimal("2.80")
    elif Decimal("85.01") <= ltv <= Decimal("90.00"):
        return True, Decimal("3.10")
    elif Decimal("90.01") <= ltv <= Decimal("95.00"):
        return True, Decimal("4.00")
    else:
        raise DecisionBusinessRuleError("LTV exceeds insurable maximum")
```

#### PIPEDA Data Handling
- **No PII in Logs**: `input_context` JSONB excludes SIN, DOB, income values. Only ratios and derived values logged.
- **Encrypted Storage**: SIN hash (SHA256) stored in `borrower_data.sin_hash`. Original SIN encrypted via `common.security.encrypt_pii()` in upstream modules.
- **Data Minimization**: Decision service only receives hashed SIN, no plaintext PII. Income values used only for calculations, not persisted in decision tables.

#### Authentication & Authorization
- All endpoints require JWT token with `sub` claim.
- `GET /audit` requires `audit_viewer` or `underwriter` scope.
- `created_by` field auto-populated from JWT `sub` claim via dependency injection.

---

### 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Retryable |
|-----------------|-------------|------------|-----------------|-----------|
| `DecisionNotFoundError` | 404 | DECISION_011 | "Decision for application {app_id} not found" | No |
| `DecisionValidationError` | 422 | DECISION_002 | "{field}: {validation_error}" | No |
| `DecisionBusinessRuleError` | 409 | DECISION_003 | "OSFI B-20 rule violated: {rule_name}" | No |
| `PolicyRuleEvaluationError` | 500 | DECISION_005 | "Rule engine failed to evaluate {rule_id}" | Yes |
| `MissingDataError` | 422 | DECISION_006 | "Required field {field} missing for {calculation}" | No |
| `CalculationError` | 500 | DECISION_007 | "Arithmetic error in {ratio} calculation: {detail}" | No |
| `PolicyConflictError` | 409 | DECISION_008 | "Conflicting policy rules: {rule_ids}" | No |
| `AuthorizationError` | 403 | DECISION_012 | "User {user_id} lacks permission for {resource}" | No |

**Error Response Structure**:
```json
{
  "detail": "GDS ratio 41.50 exceeds OSFI B-20 limit of 39.00%",
  "error_code": "DECISION_003",
  "context": {
    "application_id": "123e4567-e89b-12d3-a456-426614174000",
    "calculated_gds": 41.50,
    "threshold": 39.00,
    "rule_id": "GDS_LIMIT"
  },
  "timestamp": "2024-01-15T14:30:00Z",
  "request_id": "corr-1234567890"
}
```

**Exception Hierarchy**:
```
DecisionException(AppException)
├── DecisionNotFoundError
├── DecisionValidationError
├── DecisionBusinessRuleError
├── PolicyRuleEvaluationError
├── MissingDataError
├── CalculationError
└── PolicyConflictError
```

All exceptions logged with `structlog` at ERROR level, including `correlation_id`, `application_id`, `user_id` (hashed), but **excluding any income or PII values**.