# Decision Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Decision Service Design Plan

**Module ID**: `decision_service`  
**Feature Slug**: `decision-service-v1`  
**Document Path**: `docs/design/decision-service-v1.md`

---

## 1. Endpoints

### 1.1 POST /api/v1/decision/evaluate
Execute deterministic underwriting decision engine.

**Authentication**: Authenticated (JWT + `underwrite:execute` scope)  
**Rate Limit**: 100 requests/minute per tenant

**Request Body Schema**:
```json
{
  "application_id": "uuid",
  "borrower_profile": {
    "gross_annual_income": "Decimal",       // Must be > 0
    "gross_monthly_income": "Decimal",      // Calculated: annual / 12
    "monthly_debt_obligations": "Decimal",  // Sum of all non-mortgage debts
    "employment_type": "enum[salaried, self_employed, hourly, other]",
    "self_employed_income_verification": "enum[noa_2yr, noa_1yr, unaudited]", // Required if employment_type=self_employed
    "credit_score": "int",                  // 300-900
    "bankruptcy_history": "bool"
  },
  "property_details": {
    "property_value": "Decimal",            // Purchase price or appraised value
    "property_type": "enum[detached, semi_detached, townhouse, condo, other]",
    "property_use": "enum[primary_residence, rental_investment, second_home]"
  },
  "mortgage_terms": {
    "loan_amount": "Decimal",               // Requested mortgage principal
    "contract_rate": "Decimal",             // Annual interest rate (e.g., 5.25)
    "amortization_years": "int",            // 5-30 years
    "payment_frequency": "enum[monthly, bi_weekly, weekly]"
  },
  "policy_override_flags": ["array<string>"], // Optional: ["exception_authorized", "manual_review"]
  "request_correlation_id": "string"         // For audit tracing
}
```

**Response Schema (201 Created)**:
```json
{
  "application_id": "uuid",
  "decision_id": "uuid",
  "decision": "enum[approved, declined, exception]",
  "confidence_score": "Decimal(0-1)",       // 0.92 = 92% confidence
  "ratios": {
    "gds": "Decimal",                       // e.g., 32.50
    "tds": "Decimal",                       // e.g., 41.20
    "ltv": "Decimal"                        // e.g., 85.00
  },
  "cmhc_required": "bool",
  "cmhc_premium_amount": "Decimal|null",    // Calculated premium if LTV > 80%
  "stress_test_rate": "Decimal",            // e.g., 7.25
  "policy_flags": ["array<string>"],        // e.g., ["ltv_80_85_tier", "self_employed_verified"]
  "exceptions": [
    {
      "rule_id": "string",
      "severity": "enum[high, medium, low]",
      "message": "string",
      "mitigation_required": "bool"
    }
  ],
  "decline_reasons": ["array<string>"],     // Populated only if declined
  "conditional_approvals": ["array<string>"], // e.g., ["provide_updated_noa", "verify_downpayment_source"]
  "audit_trail": {
    "rules_evaluated": ["array<string>"],   // List of rule IDs executed
    "timestamp": "datetime",
    "model_version": "string"               // e.g., "v1.3.2-osfi-b20-2024q1"
  }
}
```

**Error Responses**:
| HTTP Status | Error Code | Detail | Trigger |
|-------------|------------|--------|---------|
| 400 | `DECISION_001` | "Invalid borrower income: must be > 0" | Income validation failure |
| 400 | `DECISION_002` | "LTV exceeds maximum insurable limit: 95%" | LTV > 95% |
| 422 | `DECISION_003` | "Missing required field: self_employed_income_verification" | Self-employed without verification method |
| 422 | `DECISION_004` | "Credit score below minimum threshold: 600" | Credit score < 600 |
| 409 | `DECISION_005` | "Decision already exists for application" | Duplicate evaluation attempt |
| 500 | `DECISION_006` | "Policy rule engine internal error" | Rule evaluation exception |

---

### 1.2 GET /api/v1/decision/{application_id}
Retrieve a decision record by application ID.

**Authentication**: Authenticated (JWT + `underwrite:read` scope)  
**Path Parameter**: `application_id: uuid`  

**Response Schema (200 OK)**:
```json
{
  "application_id": "uuid",
  "decision_id": "uuid",
  "decision": "enum[approved, declined, exception]",
  "ratios": { "gds": "Decimal", "tds": "Decimal", "ltv": "Decimal" },
  "cmhc_required": "bool",
  "stress_test_rate": "Decimal",
  "policy_flags": ["array<string>"],
  "exceptions": ["array<object>"],
  "decline_reasons": ["array<string>"],
  "conditional_approvals": ["array<string>"],
  "created_at": "datetime",
  "created_by": "string"  // User ID from JWT
}
```

**Error Responses**:
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 404 | `DECISION_007` | "Decision not found for application_id: {uuid}" |
| 403 | `DECISION_008` | "Access denied: cross-tenant data request" |

---

### 1.3 GET /api/v1/decision/{application_id}/audit
Retrieve full immutable audit trail for FINTRAC/OSFI compliance.

**Authentication**: Authenticated (JWT + `underwrite:audit` scope)  
**Path Parameter**: `application_id: uuid`  

**Response Schema (200 OK)**:
```json
{
  "application_id": "uuid",
  "decision_id": "uuid",
  "audit_logs": [
    {
      "log_id": "uuid",
      "rule_id": "string",
      "rule_name": "string",
      "rule_version": "string",
      "evaluation_result": "enum[passed, failed, exception]",
      "input_snapshot": "object",           // Redacted PII
      "output_snapshot": "object",
      "timestamp": "datetime",
      "evaluated_by": "string"              // Service principal
    }
  ],
  "retention_until": "date"                 // created_at + 5 years (FINTRAC)
}
```

**Error Responses**:
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 404 | `DECISION_009` | "Audit trail not found" |
| 403 | `DECISION_010` | "Insufficient permissions for audit access" |

---

## 2. Models & Database

### 2.1 `decision_rules` Table
Stores versioned policy rules for deterministic evaluation.

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `rule_id` | VARCHAR(50) | PRIMARY KEY | |
| `rule_name` | VARCHAR(255) | NOT NULL | |
| `rule_version` | VARCHAR(20) | NOT NULL | |
| `rule_logic` | JSONB | NOT NULL (contains formula/conditions) | GIN index |
| `rule_category` | VARCHAR(50) | NOT NULL | |
| `severity` | VARCHAR(20) | NOT NULL | |
| `is_active` | BOOLEAN | DEFAULT true | |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**Indexes**:
- `idx_decision_rules_active_version` ON (`is_active`, `rule_version`) WHERE `is_active` = true
- `idx_decision_rules_category` ON (`rule_category`)

---

### 2.2 `decisions` Table
Stores final underwriting decision (immutable after creation).

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `decision_id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | |
| `application_id` | UUID | NOT NULL, UNIQUE | `idx_decisions_application_id` |
| `decision` | VARCHAR(20) | NOT NULL | `idx_decisions_status` |
| `confidence_score` | DECIMAL(5,4) | CHECK (0 <= score <= 1) | |
| `gds_ratio` | DECIMAL(5,2) | NOT NULL | |
| `tds_ratio` | DECIMAL(5,2) | NOT NULL | |
| `ltv_ratio` | DECIMAL(5,2) | NOT NULL | |
| `cmhc_required` | BOOLEAN | NOT NULL | |
| `cmhc_premium_amount` | DECIMAL(12,2) | NULL | |
| `stress_test_rate` | DECIMAL(5,2) | NOT NULL | |
| `policy_flags` | JSONB | NOT NULL, DEFAULT '[]'::jsonb | GIN index |
| `decline_reasons` | JSONB | NULL | GIN index |
| `conditional_approvals` | JSONB | NULL | GIN index |
| `model_version` | VARCHAR(50) | NOT NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | `idx_decisions_created_at` |
| `created_by` | VARCHAR(100) | NOT NULL | |
| `tenant_id` | VARCHAR(50) | NOT NULL | `idx_decisions_tenant` |

**Constraints**:
- `chk_ratios_gds` CHECK (`gds_ratio` <= 39.00)
- `chk_ratios_tds` CHECK (`tds_ratio` <= 44.00)
- `chk_ratios_ltv_max` CHECK (`ltv_ratio` <= 95.00)

**Indexes**:
- Composite: `idx_decisions_tenant_app` ON (`tenant_id`, `application_id`)
- Composite: `idx_decisions_created_decision` ON (`created_at`, `decision`)

---

### 2.3 `decision_audit_logs` Table
Immutable audit trail for FINTRAC compliance (5-year retention).

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `log_id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | |
| `decision_id` | UUID | NOT NULL, FK → `decisions.decision_id` | `idx_audit_decision_id` |
| `rule_id` | VARCHAR(50) | NOT NULL, FK → `decision_rules.rule_id` | `idx_audit_rule_id` |
| `evaluation_result` | VARCHAR(20) | NOT NULL | |
| `input_snapshot` | JSONB | NOT NULL (PII redacted) | |
| `output_snapshot` | JSONB | NOT NULL | |
| `evaluated_by` | VARCHAR(100) | NOT NULL | |
| `timestamp` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | `idx_audit_timestamp` |
| `tenant_id` | VARCHAR(50) | NOT NULL | |

**Indexes**:
- Composite: `idx_audit_tenant_decision` ON (`tenant_id`, `decision_id`)
- `idx_audit_retention` ON (`timestamp`) for 5-year retention policy

---

## 3. Business Logic

### 3.1 Core Calculation Algorithms

**Stress Test Rate** (OSFI B-20):
```python
qualifying_rate = max(contract_rate + Decimal('2.00'), Decimal('5.25'))
```

**Monthly PITH Calculation**:
```python
# P = Principal, I = Interest, T = Taxes, H = Heat
monthly_mortgage_payment = calculate_pmt(
    rate=qualifying_rate / 12,
    nper=amortization_years * 12,
    pv=loan_amount
)
monthly_property_tax = estimated_annual_property_tax / 12
monthly_heat_cost = estimated_monthly_heat_cost  # Default: $100 if condo, $150 if detached

pith = monthly_mortgage_payment + monthly_property_tax + monthly_heat_cost
```

**GDS Ratio**:
```python
gds = (pith / gross_monthly_income) * 100
if gds > Decimal('39.00'):
    trigger_decline('GDS_EXCEEDS_39_PERCENT')
```

**TDS Ratio**:
```python
tds = ((pith + monthly_debt_obligations) / gross_monthly_income) * 100
if tds > Decimal('44.00'):
    trigger_decline('TDS_EXCEEDS_44_PERCENT')
```

**LTV Ratio**:
```python
ltv = (loan_amount / property_value) * 100
if ltv > Decimal('95.00'):
    trigger_decline('LTV_EXCEEDS_INSURABLE_LIMIT')
elif ltv > Decimal('80.00'):
    cmhc_required = True
    cmhc_premium = calculate_cmhc_premium(ltv, loan_amount)
```

### 3.2 CMHC Premium Tier Lookup
| LTV Range | Premium Rate | Calculation |
|-----------|--------------|-------------|
| ≤ 80% | 0.00% | `premium = 0` |
| 80.01% - 85% | 2.80% | `premium = loan_amount × 0.0280` |
| 85.01% - 90% | 3.10% | `premium = loan_amount × 0.0310` |
| 90.01% - 95% | 4.00% | `premium = loan_amount × 0.0400` |

### 3.3 Self-Employed Income Calculation Rules
- **Verified by NOA (2-year average)**: Use average of last 2 years T1 income, discount by 15%
- **Verified by NOA (1-year)**: Use most recent year T1 income, discount by 25%
- **Unaudited**: Not acceptable for GDS/TDS calculation → automatic `exception` status
- **Minimum credit score for self-employed**: 680 (vs. 600 for salaried)

### 3.4 Decision State Machine & Rules Engine

**Decision Tree**:
```
START → Validate Input → Calculate Ratios → Evaluate Rules →
    ├─> ALL PASS → APPROVED
    ├─> HIGH SEVERITY FAIL → DECLINED (with prioritized reason)
    └─> MEDIUM/LOW FAIL → EXCEPTION (requires manual review)
```

**Decline Reason Prioritization**:
1. **Critical** (immediate decline, no exception):
   - LTV > 95%
   - Credit score < 600 (or < 680 for self-employed)
   - Bankruptcy within 7 years
   - Invalid property type (e.g., commercial)

2. **High Severity** (decline unless exception authorized):
   - TDS > 44%
   - GDS > 39%
   - LTV > 85% + credit score < 650

3. **Medium Severity** (exception with conditions):
   - LTV 80.01-85% + insufficient downpayment source verification
   - Self-employed with 1-year NOA only
   - Property value uncertainty > 10%

### 3.5 Conditional Approval Criteria
If `decision = approved` but conditions exist:
- `conditional_approvals` array populated with:
  - `"provide_updated_noa"` (if self-employed income > 30% of total)
  - `"verify_downpayment_source_90_days"` (if downpayment > 20% of net worth)
  - `"submit_property_appraisal"` (if purchase price deviates > 15% from automated valuation)
  - `"confirm_employment_letter"` (if employment tenure < 2 years)

---

## 4. Migrations

### Migration: `001_create_decision_service_tables.py`

**New Tables**:
```python
# decision_rules
op.create_table('decision_rules', ...)

# decisions
op.create_table('decisions', ...)

# decision_audit_logs
op.create_table('decision_audit_logs', ...)
```

**Indexes**:
```python
# GIN indexes for JSONB
op.create_index('idx_decisions_policy_flags_gin', 'decisions', ['policy_flags'], postgresql_using='gin')
op.create_index('idx_decisions_decline_reasons_gin', 'decisions', ['decline_reasons'], postgresql_using='gin')

# Composite indexes for tenant isolation
op.create_index('idx_decisions_tenant_app', 'decisions', ['tenant_id', 'application_id'])
op.create_index('idx_audit_tenant_decision', 'decision_audit_logs', ['tenant_id', 'decision_id'])
```

**Data Migration**:
- Seed initial rule set from `/migrations/data/initial_decision_rules.json`
- Insert OSFI B-20 baseline rules (GDS, TDS, LTV limits)
- Insert CMHC premium tier rules

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Stress Test Enforcement**: Qualifying rate calculation logged in `decision_audit_logs.input_snapshot`
- **Ratio Limits**: Hard constraints at DB level (`chk_ratios_gds`, `chk_ratios_tds`)
- **Auditability**: Every rule evaluation creates immutable audit log entry with timestamp, rule version, and result
- **Model Versioning**: `model_version` field tracks which policy version was applied for reproducibility

### 5.2 FINTRAC Compliance
- **Immutable Audit Trail**: `decision_audit_logs` table has no UPDATE/DELETE operations; INSERT only
- **5-Year Retention**: `retention_until` calculated as `created_at + INTERVAL '5 years'`
- **Transaction Threshold**: If `loan_amount >= CAD 10,000`, automatically add `LARGE_TRANSACTION` flag to `policy_flags`
- **Identity Verification Logging**: Log that verification occurred (not the data) in `audit_trail.rules_evaluated`

### 5.3 CMHC Insurance Requirements
- **LTV Calculation**: Use `Decimal` with precision=10, scale=2; no float arithmetic
- **Premium Tier Lookup**: Deterministic mapping in `decision_rules.rule_logic` JSONB
- **Insurance Flagging**: `cmhc_required` boolean set when `ltv > 80.00`
- **Premium Amount**: Calculated and stored as `Decimal` with 2 decimal places

### 5.4 PIPEDA Data Handling
- **No PII in Logs**: `input_snapshot` redacts SIN, DOB, full name, account numbers before persistence
- **Encrypted Fields**: Not applicable in decision service (works with extracted, tokenized data)
- **Data Minimization**: Only receives required underwriting fields; rejects requests with extraneous PII
- **Logging**: `structlog` correlation_id tracked; no sensitive data in log messages

### 5.5 Authentication & Authorization
- **JWT Validation**: `verify_token()` from `common/security.py` enforced on all endpoints
- **Scope Requirements**:
  - `POST /evaluate`: `underwrite:execute`
  - `GET /{id}`: `underwrite:read`
  - `GET /{id}/audit`: `underwrite:audit`
- **Tenant Isolation**: `tenant_id` extracted from JWT claim; all queries filter by tenant

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy
All exceptions inherit from `AppException` base class in `common/exceptions.py`.

| Exception Class | HTTP Status | Error Code | Message Pattern | Retryable |
|-----------------|-------------|------------|-----------------|-----------|
| `DecisionNotFoundError` | 404 | `DECISION_007` | "Decision not found for application_id: {uuid}" | No |
| `DecisionValidationError` | 422 | `DECISION_003` | "{field}: {reason}" | No |
| `DecisionBusinessRuleError` | 409 | `DECISION_005` | "Business rule violated: {rule_id}" | No |
| `DecisionRatioExceededError` | 400 | `DECISION_002` | "{ratio_type} exceeds limit: {value} > {limit}" | No |
| `DecisionConflictError` | 409 | `DECISION_005` | "Decision already exists for application" | No |
| `DecisionRuleEngineError` | 500 | `DECISION_006` | "Policy rule engine internal error" | Yes |
| `DecisionTenantMismatchError` | 403 | `DECISION_008` | "Cross-tenant access denied" | No |

### Error Response Format
All error responses follow structured format:
```json
{
  "detail": "Decision not found for application_id: 123e4567-e89b-12d3-a456-426614174000",
  "error_code": "DECISION_007",
  "correlation_id": "corr_01HQZ...",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### Edge Cases & Error Scenarios
- **Division by Zero**: If `gross_monthly_income = 0`, raise `DecisionValidationError` with code `DECISION_001`
- **NaN Ratios**: If LTV calculation results in NaN, log error and raise `DecisionRuleEngineError`
- **Missing Rule**: If referenced `rule_id` not in `decision_rules`, raise `DecisionRuleEngineError`
- **Concurrent Evaluation**: Use `INSERT ... ON CONFLICT` to prevent duplicate decisions; return `DecisionConflictError`
- **Rate Limit Exceeded**: FastAPI middleware returns 429 with `DECISION_011` (configured in `routes.py`)

---

## 7. Additional Design Considerations

### 7.1 Caching Strategy
- **Policy Rules Cache**: Redis cache for active `decision_rules` with 5-minute TTL; key: `decision:rules:active:{version}`
- **Decision Cache**: Do NOT cache decisions (FINTRAC immutability requirement)

### 7.2 Performance Targets
- **P99 Latency**: < 200ms for `/evaluate` endpoint
- **Throughput**: 500 decisions/second per instance
- **Database**: Connection pooling with `sqlalchemy.AsyncEngine` (min 5, max 20)

### 7.3 Testing Requirements
- **Unit Tests**: 100% coverage on calculation functions; mock all DB calls
- **Integration Tests**: Test full flow with PostgreSQL; verify audit log immutability
- **Regulatory Tests**: Validate OSFI B-20 stress test scenarios (rate + 2% vs 5.25%)
- **Benchmark Tests**: Load test with 1000 concurrent decision evaluations

---

**Design Version**: 1.0.0  
**Last Updated**: 2024-01-15  
**Compliance Review**: OSFI B-20, FINTRAC, CMHC, PIPEDA  
**Next Steps**: Implement models.py, schemas.py, services.py, routes.py, exceptions.py in `modules/decision_service/`