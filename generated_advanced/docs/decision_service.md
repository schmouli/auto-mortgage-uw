# Decision Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Decision Service Design Plan

**File:** `docs/design/decision-service.md`  
**Module:** `decision_service`  
**Feature Slug:** `decision-service`

---

## 1. Endpoints

### `POST /api/v1/decision/evaluate`
Run synchronous underwriting decision evaluation.

**Request Schema**
```python
class DecisionEvaluateRequest(BaseModel):
    application_id: UUID
    borrower_profile: BorrowerProfile
    property_details: PropertyDetails
    product_details: ProductDetails
    policy_context: Optional[PolicyContext] = None

class BorrowerProfile(BaseModel):
    gross_annual_income: Decimal  # Validated upstream, no PII
    monthly_debt_payments: Decimal
    monthly_property_tax: Decimal
    monthly_heating: Decimal
    credit_score: Optional[int] = None
    employment_type: Literal["employed", "self_employed"]

class PropertyDetails(BaseModel):
    property_value: Decimal
    mortgage_amount: Decimal

class ProductDetails(BaseModel):
    contract_rate: Decimal
    amortization_years: int  # Max 30 per OSFI
    payment_frequency: Literal["monthly", "bi_weekly"]
```

**Response Schema**
```python
class DecisionEvaluateResponse(BaseModel):
    application_id: UUID
    decision: Literal["approved", "declined", "exception", "conditional"]
    confidence_score: Decimal  # 0.0-1.0, see Business Logic
    ratios: RatioSummary
    cmhc_required: bool
    stress_test_rate: Decimal
    policy_flags: List[str]
    conditions: List[str]
    decline_reasons: List[str]
    audit_snapshot: AuditSnapshot
    created_at: datetime

class RatioSummary(BaseModel):
    gds: Decimal  # 10,4 precision
    tds: Decimal
    ltv: Decimal

class AuditSnapshot(BaseModel):
    rules_evaluated: List[str]
    timestamp: datetime
    model_version: str
```

**Error Responses**
| Status | Error Code | Detail Pattern | Trigger |
|--------|------------|----------------|---------|
| `400` | `DECISION_001` | "Invalid input: {field} must be positive" | Negative financial value |
| `422` | `DECISION_002` | "Validation failed: amortization exceeds 30 years" | OSFI limit violation |
| `422` | `DECISION_002` | "Validation failed: LTV exceeds 100%" | Impossible loan |
| `500` | `DECISION_003` | "Calculation error: division by zero" | Income = 0 |
| `500` | `DECISION_003` | "Policy rule execution failed: {detail}" | Unexpected error |

**Auth:** `authenticated` (scope: `underwrite`)

---

### `GET /api/v1/decision/{application_id}`
Retrieve stored decision record.

**Path Parameter:** `application_id: UUID`

**Response Schema:** `DecisionEvaluateResponse` (from above)

**Error Responses**
| Status | Error Code | Detail Pattern |
|--------|------------|----------------|
| `404` | `DECISION_004` | "Decision for application {id} not found" |

**Auth:** `authenticated` (scope: `read`)

---

### `GET /api/v1/decision/{application_id}/audit`
Retrieve full immutable audit trail.

**Path Parameter:** `application_id: UUID`

**Response Schema**
```python
class DecisionAuditResponse(BaseModel):
    application_id: UUID
    events: List[AuditEvent]

class AuditEvent(BaseModel):
    event_type: str  # "rule_evaluated", "ratio_calculated", "decision_finalized"
    event_data: Dict[str, Any]  # Calculation breakdown, no PII
    timestamp: datetime
    model_version: str
```

**Error Responses**
| Status | Error Code | Detail Pattern |
|--------|------------|----------------|
| `404` | `DECISION_005` | "Audit trail for application {id} not found" |

**Auth:** `authenticated` (scope: `audit`)

---

## 2. Models & Database

### `decision_records` Table
| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `UUID` | `PRIMARY KEY` | |
| `application_id` | `UUID` | `NOT NULL, UNIQUE` | `UNIQUE` |
| `decision` | `VARCHAR(12)` | `CHECK IN (...)` | |
| `confidence_score` | `NUMERIC(5,4)` | `NOT NULL` | |
| `gds_ratio` | `NUMERIC(10,4)` | `NOT NULL` | |
| `tds_ratio` | `NUMERIC(10,4)` | `NOT NULL` | |
| `ltv_ratio` | `NUMERIC(10,4)` | `NOT NULL` | |
| `cmhc_required` | `BOOLEAN` | `NOT NULL` | |
| `stress_test_rate` | `NUMERIC(10,4)` | `NOT NULL` | |
| `policy_flags` | `JSONB` | `NOT NULL, DEFAULT '[]'` | `GIN` |
| `conditions` | `JSONB` | `NOT NULL, DEFAULT '[]'` | `GIN` |
| `decline_reasons` | `JSONB` | `NOT NULL, DEFAULT '[]'` | `GIN` |
| `rules_evaluated` | `JSONB` | `NOT NULL` | |
| `model_version` | `VARCHAR(20)` | `NOT NULL` | |
| `created_at` | `TIMESTAMP` | `NOT NULL, DEFAULT NOW()` | `BTREE` |
| `updated_at` | `TIMESTAMP` | `NOT NULL, DEFAULT NOW()` | |

**Relationships:** None (standalone service)

### `decision_audit_log` Table
| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `UUID` | `PRIMARY KEY` | |
| `decision_record_id` | `UUID` | `FOREIGN KEY decision_records.id` | `BTREE` |
| `event_type` | `VARCHAR(30)` | `NOT NULL` | |
| `event_data` | `JSONB` | `NOT NULL` | `GIN` |
| `timestamp` | `TIMESTAMP` | `NOT NULL, DEFAULT NOW()` | `BTREE` |
| `model_version` | `VARCHAR(20)` | `NOT NULL` | |

**Retention:** 5-year retention enforced via PostgreSQL partition policy on `timestamp` (quarterly partitions). **No DELETE operations** permitted by application role.

---

## 3. Business Logic

### Calculation Algorithms

**Stress Test Rate (OSFI B-20)**
```python
qualifying_rate = max(contract_rate + Decimal('2.00'), Decimal('5.25'))
log.info("stress_test_calculated", contract_rate=contract_rate, qualifying_rate=qualifying_rate)
```

**LTV & CMHC Requirement (CMHC)**
```python
ltv = (mortgage_amount / property_value) * Decimal('100')
ltv = ltv.quantize(Decimal('0.01'))

if ltv > Decimal('95'):
    decline_reasons.append("LTV exceeds 95% insured maximum")
elif ltv > Decimal('80'):
    cmhc_required = True
    if Decimal('80.01') <= ltv <= Decimal('85.00'): premium_rate = Decimal('2.80')
    elif Decimal('85.01') <= ltv <= Decimal('90.00'): premium_rate = Decimal('3.10')
    elif Decimal('90.01') <= ltv <= Decimal('95.00'): premium_rate = Decimal('4.00')
    # Log tier selection
else:
    cmhc_required = False
```

**PITH Calculation**
```python
# Monthly payment using stress_test_rate
monthly_rate = qualifying_rate / Decimal('100') / Decimal('12')
num_payments = amortization_years * 12
mortgage_payment = mortgage_amount * (monthly_rate * (1 + monthly_rate) ** num_payments) / ((1 + monthly_rate) ** num_payments - 1)

pith = mortgage_payment + monthly_property_tax + monthly_heating
log.info("pith_calculated", pith=pith, breakdown={...})
```

**GDS/TDS (OSFI B-20)**
```python
gross_monthly_income = gross_annual_income / Decimal('12')
gds = (pith / gross_monthly_income) * Decimal('100')
tds = ((pith + monthly_debt_payments) / gross_monthly_income) * Decimal('100')

# Log full breakdown for audit
log.info("ratio_calculated", type="gds", numerator=pith, denominator=gross_monthly_income, result=gds)
log.info("ratio_calculated", type="tds", numerator=pith+debt, denominator=gross_monthly_income, result=tds)

if gds > Decimal('39'): decline_reasons.append(f"GDS {gds}% exceeds 39% limit")
if tds > Decimal('44'): decline_reasons.append(f"TDS {tds}% exceeds 44% limit")
```

### Decision Matrix
| Condition | Decision | Confidence | Conditions | Exceptions |
|-----------|----------|------------|------------|------------|
| No hard limit violations, no flags | `approved` | `1.00` | `[]` | `[]` |
| No hard limit violations, minor flags (e.g., credit_score < 680) | `conditional` | `0.85` | `["provide_pay_stub"]` | `[]` |
| No hard limit violations, major flags (e.g., self_employed) | `exception` | `0.60` | `[]` | `["manual_review_required"]` |
| Any hard limit violated | `declined` | `1.00` | `[]` | `[]` |

**Decline Reason Prioritization:** LTV > GDS > TDS > Credit > Loan-to-Income. Return max 3 reasons.

**Self-Employed Income:** Service accepts pre-calculated `gross_annual_income` from Income Verification module. Flag `self_employed` triggers `exception` decision for manual review; no calculation changes.

---

## 4. Migrations

### Alembic Revision: `create_decision_service_tables`

**Operations:**
```python
op.create_table('decision_records', ...)
op.create_table('decision_audit_log', ...)
op.create_index('ix_decision_records_application_id', 'decision_records', ['application_id'], unique=True)
op.create_index('ix_decision_records_created_at', 'decision_records', ['created_at'])
op.create_index('ix_decision_audit_log_timestamp', 'decision_audit_log', ['timestamp'])
op.create_index('ix_decision_audit_log_decision_record_id', 'decision_audit_log', ['decision_record_id'])
```

**No Data Migration:** Module is new.

---

## 5. Security & Compliance

### OSFI B-20
- **Stress Test:** Calculation logged with `contract_rate` and `qualifying_rate`.
- **Ratio Audits:** Every GDS/TDS calculation logs numerator, denominator, result.
- **Hard Limits:** Enforced at code level; violations stored in `decline_reasons`.

### FINTRAC
- **Immutability:** `decision_audit_log` table has no UPDATE/DELETE endpoints.
- **Retention:** 5-year retention via PostgreSQL partitioning on `timestamp`. Application role lacks `DELETE` privilege.
- **No PII:** Service contract prohibits SIN/DOB in request payload.

### CMHC
- **LTV Precision:** Calculated with `Decimal` to 2 decimal places.
- **Premium Tiers:** Lookup table stored in `common.config.PolicyConfig`; changes require new migration.

### PIPEDA
- **Data Minimization:** Request schema excludes PII; only financial metrics.
- **Logging:** `structlog` configuration masks fields labeled `pii=True`; no such fields exist in this module.
- **Encryption:** Not required (no PII at rest).

### AuthZ Matrix
| Endpoint | Required Scope | Notes |
|----------|----------------|-------|
| `POST /evaluate` | `underwrite` | Service-to-service or underwriter role |
| `GET /{id}` | `read` | Originator or underwriter role |
| `GET /{id}/audit` | `audit` | Compliance officer role |

---

## 6. Error Codes & HTTP Responses

**Exception Classes (modules/decision_service/exceptions.py)**
```python
class DecisionValidationError(AppException): ...
class DecisionCalculationError(AppException): ...
class DecisionNotFoundError(AppException): ...
class DecisionAuditNotFoundError(AppException): ...
```

**Mapping Table**
| Exception | HTTP | Error Code | Message Template |
|-----------|------|------------|------------------|
| `DecisionValidationError` | `422` | `DECISION_001` | "Validation error: {field} {detail}" |
| `DecisionCalculationError` | `500` | `DECISION_002` | "Calculation failed: {detail}" |
| `DecisionNotFoundError` | `404` | `DECISION_003` | "Decision record {application_id} not found" |
| `DecisionAuditNotFoundError` | `404` | `DECISION_004` | "Audit trail for {application_id} not found" |

**Response Format**
```json
{
  "detail": "GDS ratio 42.15% exceeds regulatory limit",
  "error_code": "DECISION_001",
  "metadata": {
    "application_id": "123e4567-e89b-12d3-a456-426614174000",
    "violating_ratio": "gds",
    "calculated_value": "42.15"
  }
}
```

---

## 7. Additional Design Notes

### Exception Handling Workflow
- `decision = "exception"` publishes `DecisionReferralEvent` to message queue (`referral.events` exchange).
- Event payload: `{application_id, reasons: policy_flags, timestamp}`.
- Referral Service consumes event and creates manual review task.

### Conditional Approval Criteria
- Generated from policy flags: `low_credit_score` → `["provide_credit_explanation"]`.
- Stored in `conditions` JSONB; fulfillment tracked by Application Module.

### Confidence Score Logic
- `1.00` if no flags and data complete.
- `-0.10` per major flag (self-employed, high LTV).
- `-0.05` per minor flag (credit score < 680).
- Minimum `0.50` for exception decisions.

### Observability
- **Metrics:** `decision_total{decision_type}`, `ratio_calculation_duration_seconds`, `policy_flag_total{flag_name}`.
- **Tracing:** OTel span per rule evaluation.
- **Logging:** `structlog` with `correlation_id`, `application_id`; never log `borrower_profile` raw dict.

### Testing Strategy
- **Unit:** Mock all inputs; verify calculation precision to 4 decimal places.
- **Integration:** Use test DB; verify audit log immutability and 5-year partition query performance.
- **Markers:** `@pytest.mark.unit` for rule logic, `@pytest.mark.integration` for DB constraints.

---