# Underwriting Engine
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Underwriting Engine Module Design Plan

**Module Path**: `mortgage_underwriting/modules/underwriting/`  
**Design Document**: `docs/design/underwriting-engine.md`  
**Last Updated**: 2024

---

## 1. Endpoints

### 1.1 POST /api/v1/underwriting/calculate
Run qualification calculations without persisting results.

**Authentication**: Authenticated user (underwriter or system)

**Request Body** (`UnderwritingCalculationRequest`):
```python
{
  "property_value": Decimal,  # required, > 0
  "loan_amount": Decimal,     # required, > 0
  "contract_rate": Decimal,   # required, > 0 (e.g., 0.0525 for 5.25%)
  "gross_monthly_income": Decimal,  # required, > 0
  "monthly_property_tax": Decimal,  # required, >= 0
  "monthly_heating": Decimal,       # required, >= 0
  "monthly_condo_fees": Decimal = 0,  # optional, >= 0
  "other_monthly_debts": List[DebtItem] = [],  # optional
  "rental_income": Decimal = 0,     # optional, >= 0
  "rental_property_expenses": Decimal = 0,  # optional, >= 0
  "is_self_employed": bool = False,  # optional
  "self_employed_income_verified": bool = False,  # optional
  "down_payment_amount": Decimal,   # required, >= 0
  "amortization_years": int = 25    # optional, 5-30
}

# DebtItem schema:
{
  "debt_type": str,  # e.g., "credit_card", "car_loan"
  "monthly_payment": Decimal,  # required, > 0
  "balance": Decimal,  # optional, >= 0
  "is_secured": bool  # optional
}
```

**Response** (`UnderwritingCalculationResponse`):
```python
{
  "qualifies": bool,
  "decision": Literal["APPROVED", "CONDITIONAL", "DECLINED"],
  "gds_ratio": Decimal,  # e.g., 0.35 for 35%
  "tds_ratio": Decimal,
  "ltv_ratio": Decimal,
  "cmhc_required": bool,
  "cmhc_premium_amount": Decimal,
  "qualifying_rate": Decimal,
  "max_mortgage_amount": Decimal,
  "decline_reasons": List[DeclineReasonSchema],
  "conditions": List[ConditionSchema],
  "stress_test_passed": bool,
  "calculation_breakdown": Dict[str, Decimal]  # audit trail
}

# DeclineReasonSchema:
{
  "reason_code": str,  # e.g., "GDS_EXCEEDS_THRESHOLD"
  "reason_text": str,
  "priority": int
}

# ConditionSchema:
{
  "condition_code": str,  # e.g., "SELF_EMPLOYED_INCOME_VERIFICATION"
  "condition_text": str
}
```

**Error Responses**:
- `400 Bad Request`: `UNDERWRITING_004` - "Invalid calculation parameters: {detail}"
- `401 Unauthorized`: `AUTH_001` - "Authentication required"
- `403 Forbidden`: `AUTH_002` - "Insufficient permissions"
- `422 Unprocessable Entity`: `UNDERWRITING_002` - Field validation errors

---

### 1.2 POST /api/v1/underwriting/applications/{application_id}/evaluate
Fetch application data, run full evaluation, and persist results.

**Authentication**: Authenticated underwriter

**Path Parameters**:
- `application_id`: UUID - existing mortgage application ID

**Request Body** (`UnderwritingEvaluationRequest`):
```python
{
  "evaluation_options": {
    "include_rental_income": bool = True,
    "include_additional_properties": bool = True,
    "use_verified_income_only": bool = False
  }
}
```

**Response** (`UnderwritingResultSchema`): Same as `UnderwritingCalculationResponse` with additional fields:
```python
{
  "evaluation_id": UUID,
  "application_id": UUID,
  "status": Literal["draft", "completed", "overridden"],
  "created_at": datetime,
  "created_by": str,  # user_id
  # ... all fields from UnderwritingCalculationResponse
}
```

**Error Responses**:
- `400 Bad Request`: `UNDERWRITING_005` - "Application data incomplete: {missing_fields}"
- `401 Unauthorized`: `AUTH_001`
- `403 Forbidden`: `AUTH_002`
- `404 Not Found`: `UNDERWRITING_001` - "Application {id} not found"
- `409 Conflict`: `UNDERWRITING_003` - "Evaluation already exists for application {id}"
- `422 Unprocessable Entity`: `UNDERWRITING_002`

---

### 1.3 GET /api/v1/underwriting/applications/{application_id}/result
Retrieve persisted underwriting evaluation.

**Authentication**: Authenticated user

**Path Parameters**:
- `application_id`: UUID

**Response** (`UnderwritingResultSchema`): Same as above

**Error Responses**:
- `401 Unauthorized`: `AUTH_001`
- `403 Forbidden`: `AUTH_002`
- `404 Not Found`: `UNDERWRITING_001` - "No underwriting result found for application {id}"

---

### 1.4 POST /api/v1/underwriting/applications/{application_id}/override
Admin override of underwriting decision with mandatory audit trail.

**Authentication**: Admin-only (role-based)

**Path Parameters**:
- `application_id`: UUID

**Request Body** (`UnderwritingOverrideRequest`):
```python
{
  "override_reason": str,  # required, min 20 chars
  "new_decision": Literal["APPROVED", "CONDITIONAL", "DECLINED"],  # optional
  "bypass_conditions": List[str] = []  # optional, condition codes to waive
}
```

**Response** (`UnderwritingResultSchema`): Updated evaluation with override metadata:
```python
{
  # ... all standard fields
  "status": "overridden",
  "override": {
    "overridden_by": str,
    "overridden_at": datetime,
    "reason": str,
    "bypassed_conditions": List[str]
  }
}
```

**Error Responses**:
- `400 Bad Request`: `UNDERWRITING_006` - "Override reason must be at least 20 characters"
- `401 Unauthorized`: `AUTH_001`
- `403 Forbidden`: `AUTH_007` - "Admin privileges required"
- `404 Not Found`: `UNDERWRITING_001`
- `409 Conflict`: `UNDERWRITING_008` - "Override not allowed on {decision} evaluations"
- `422 Unprocessable Entity`: `UNDERWRITING_002`

---

## 2. Models & Database

### 2.1 Table: `underwriting_evaluations`
Stores primary underwriting results with full audit trail.

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | - |
| `application_id` | UUID | NOT NULL, FK(applications.id) | IX_application_id |
| `status` | VARCHAR(20) | NOT NULL, CHECK IN ('draft','completed','overridden') | IX_status |
| `decision` | VARCHAR(20) | NOT NULL, CHECK IN ('APPROVED','CONDITIONAL','DECLINED') | IX_decision |
| `gds_ratio` | DECIMAL(5,4) | NOT NULL | - |
| `tds_ratio` | DECIMAL(5,4) | NOT NULL | - |
| `ltv_ratio` | DECIMAL(5,4) | NOT NULL | IX_ltv |
| `cmhc_required` | BOOLEAN | NOT NULL | IX_cmhc |
| `cmhc_premium_amount` | DECIMAL(12,2) | NOT NULL, DEFAULT 0 | - |
| `qualifying_rate` | DECIMAL(5,4) | NOT NULL | - |
| `max_mortgage_amount` | DECIMAL(12,2) | NOT NULL | - |
| `stress_test_passed` | BOOLEAN | NOT NULL | IX_stress_test |
| `calculation_breakdown` | JSONB | NOT NULL | GIN index |
| `decline_reason_count` | INTEGER | NOT NULL, DEFAULT 0 | - |
| `condition_count` | INTEGER | NOT NULL, DEFAULT 0 | - |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | IX_created_at |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | - |
| `created_by` | VARCHAR(50) | NOT NULL | IX_created_by |
| `overridden_at` | TIMESTAMPTZ | NULL | - |
| `overridden_by` | VARCHAR(50) | NULL | - |
| `override_reason` | TEXT | NULL | - |

**Indexes**:
- Composite: `(application_id, created_at DESC)` for latest result queries
- Composite: `(decision, ltv_ratio)` for portfolio risk analysis
- GIN index on `calculation_breakdown` for audit log queries

---

### 2.2 Table: `underwriting_decline_reasons`
Master list of decline reason templates.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PRIMARY KEY |
| `reason_code` | VARCHAR(50) | UNIQUE, NOT NULL |
| `reason_text` | TEXT | NOT NULL |
| `priority` | INTEGER | NOT NULL, UNIQUE |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true |

**Seed Data**:
```sql
INSERT INTO underwriting_decline_reasons VALUES
  ('LTV_EXCEEDS_MAXIMUM', 'Loan-to-value ratio exceeds maximum allowable threshold', 1),
  ('GDS_EXCEEDS_THRESHOLD', 'Gross Debt Service ratio exceeds 39% OSFI limit', 2),
  ('TDS_EXCEEDS_THRESHOLD', 'Total Debt Service ratio exceeds 44% OSFI limit', 3),
  ('STRESS_TEST_FAILED', 'Application does not pass OSFI B-20 stress test', 4),
  ('INSUFFICIENT_DOWN_PAYMENT', 'Down payment does not meet property value tier requirements', 5),
  ('UNVERIFIED_RENTAL_INCOME', 'Rental income cannot be verified', 6),
  ('SELF_EMPLOYED_INCOME_UNVERIFIED', 'Self-employed income verification insufficient', 7);
```

---

### 2.3 Table: `evaluation_decline_reasons`
Junction table linking evaluations to decline reasons.

| Column | Type | Constraints |
|--------|------|-------------|
| `evaluation_id` | UUID | FK(underwriting_evaluations.id), PK |
| `decline_reason_id` | UUID | FK(underwriting_decline_reasons.id), PK |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

**Index**: Composite on `(evaluation_id, created_at)`

---

### 2.4 Table: `underwriting_conditions`
Master list of conditional approval requirements.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PRIMARY KEY |
| `condition_code` | VARCHAR(50) | UNIQUE, NOT NULL |
| `condition_text` | TEXT | NOT NULL |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true |

**Seed Data**:
```sql
INSERT INTO underwriting_conditions VALUES
  ('SELF_EMPLOYED_INCOME_VERIFICATION', 'Provide 2 years NOA and accountant letter'),
  ('RENTAL_INCOME_VERIFICATION', 'Provide executed lease agreement and bank statements'),
  ('ADDITIONAL_PROPERTY_DEBT_VERIFICATION', 'Disclose all other property debts'),
  ('APPRAISAL_REQUIRED', 'Subject property appraisal required'),
  ('DOWN_PAYMENT_SOURCE_VERIFICATION', 'Verify source of down payment funds');
```

---

### 2.5 Table: `evaluation_conditions`
Junction table for conditions applied to evaluations.

| Column | Type | Constraints |
|--------|------|-------------|
| `evaluation_id` | UUID | FK(underwriting_evaluations.id), PK |
| `condition_id` | UUID | FK(underwriting_conditions.id), PK |
| `is_waived` | BOOLEAN | NOT NULL, DEFAULT false |
| `waived_by` | VARCHAR(50) | NULL |
| `waived_at` | TIMESTAMPTZ | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

---

### 2.6 Table: `underwriting_overrides`
Immutable audit trail for all overrides (FINTRAC compliance).

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PRIMARY KEY |
| `evaluation_id` | UUID | NOT NULL, FK(underwriting_evaluations.id) |
| `original_decision` | VARCHAR(20) | NOT NULL |
| `new_decision` | VARCHAR(20) | NOT NULL |
| `override_reason` | TEXT | NOT NULL |
| `bypassed_conditions` | JSONB | NOT NULL, DEFAULT '[]' |
| `overridden_by` | VARCHAR(50) | NOT NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

**Index**: Composite `(evaluation_id, created_at DESC)`

---

## 3. Business Logic

### 3.1 Core Algorithms

#### Stress Test Calculation (OSFI B-20)
```python
qualifying_rate = max(contract_rate + Decimal('0.02'), Decimal('0.0525'))
# Use this rate for all debt service calculations
```

#### Monthly Mortgage Payment (PITH)
```python
# Standard annuity formula using qualifying_rate
n = amortization_years * 12
monthly_rate = qualifying_rate / 12
pith = loan_amount * (monthly_rate * (1 + monthly_rate)**n) / ((1 + monthly_rate)**n - 1)
```

#### GDS/TDS Ratios
```python
# GDS = (PITH + Property Tax + Heating + 50% Condo Fees) / Gross Monthly Income
gds_numerator = pith + monthly_property_tax + monthly_heating + (monthly_condo_fees * Decimal('0.5'))
gds_ratio = gds_numerator / gross_monthly_income

# TDS = (GDS Numerator + All Other Debts + Rental Property Expenses) / Gross Monthly Income
total_debts = sum(d.monthly_payment for d in other_monthly_debts)
tds_numerator = gds_numerator + total_debts + rental_property_expenses
tds_ratio = tds_numerator / gross_monthly_income
```

#### LTV & Down Payment Tiers (CMHC)
```python
ltv_ratio = loan_amount / property_value

# Down payment validation
if property_value <= 500000:
    min_down = property_value * Decimal('0.05')
elif property_value <= 1500000:
    min_down = (500000 * Decimal('0.05')) + ((property_value - 500000) * Decimal('0.10'))
else:
    min_down = property_value * Decimal('0.20')

down_payment_valid = down_payment_amount >= min_down
```

#### CMHC Insurance Premium
```python
if ltv_ratio > Decimal('0.80'):
    cmhc_required = True
    if Decimal('0.8001') <= ltv_ratio <= Decimal('0.85'):
        premium_rate = Decimal('0.0280')
    elif Decimal('0.8501') <= ltv_ratio <= Decimal('0.90'):
        premium_rate = Decimal('0.0310')
    elif Decimal('0.9001') <= ltv_ratio <= Decimal('0.95'):
        premium_rate = Decimal('0.0400')
    else:
        premium_rate = Decimal('0')
    cmhc_premium_amount = loan_amount * premium_rate
else:
    cmhc_required = False
    cmhc_premium_amount = Decimal('0')
```

### 3.2 Decision Tree

```python
decline_reasons = []
conditions = []

# 1. LTV Check
if ltv_ratio > Decimal('0.95'):
    decline_reasons.append('LTV_EXCEEDS_MAXIMUM')

# 2. Down Payment Check
if not down_payment_valid:
    decline_reasons.append('INSUFFICIENT_DOWN_PAYMENT')

# 3. Stress Test
stress_test_passed = (gds_ratio_at_qualifying_rate <= Decimal('0.39') and 
                      tds_ratio_at_qualifying_rate <= Decimal('0.44'))
if not stress_test_passed:
    decline_reasons.append('STRESS_TEST_FAILED')

# 4. GDS/TDS Thresholds
if gds_ratio > Decimal('0.39'):
    decline_reasons.append('GDS_EXCEEDS_THRESHOLD')
if tds_ratio > Decimal('0.44'):
    decline_reasons.append('TDS_EXCEEDS_THRESHOLD')

# 5. Conditional Logic
if is_self_employed and not self_employed_income_verified:
    conditions.append('SELF_EMPLOYED_INCOME_VERIFICATION')
if rental_income > 0:
    conditions.append('RENTAL_INCOME_VERIFICATION')

# Final Decision
if decline_reasons:
    decision = "DECLINED"
elif conditions:
    decision = "CONDITIONAL"
else:
    decision = "APPROVED"

qualifies = decision in ["APPROVED", "CONDITIONAL"]
```

### 3.3 State Machine

**Evaluation Status Lifecycle**:
```
draft → completed → overridden
     ↘─────────────↗ (admin action)
```

- **draft**: Calculation performed but not finalized
- **completed**: Final evaluation persisted, decision locked
- **overridden**: Admin has overridden decision, original preserved in audit trail

**Transitions**:
1. `POST /calculate` → No state (transient)
2. `POST /evaluate` → draft → completed (atomic transaction)
3. `POST /override` → completed → overridden (immutable, creates audit record)

---

### 3.4 Validation Rules

| Rule | Threshold | Error Code | Action |
|------|-----------|------------|--------|
| Min Property Value | $50,000 | `VAL_001` | Reject calculation |
| Max Property Value | $5,000,000 | `VAL_002` | Reject calculation |
| Max Amortization | 30 years | `VAL_003` | Default to 25 years |
| Min Contract Rate | 0.01% | `VAL_004` | Reject calculation |
| Max Contract Rate | 20% | `VAL_005` | Reject calculation |
| Min Gross Income | $1,000/month | `VAL_006` | Warning flag |
| Max Debt Items | 20 per application | `VAL_007` | Truncate with warning |

---

## 4. Migrations

### 4.1 New Tables
```sql
-- Create underwriting_evaluations table
CREATE TABLE underwriting_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE RESTRICT,
    status VARCHAR(20) NOT NULL CHECK (status IN ('draft', 'completed', 'overridden')),
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('APPROVED', 'CONDITIONAL', 'DECLINED')),
    gds_ratio DECIMAL(5,4) NOT NULL,
    tds_ratio DECIMAL(5,4) NOT NULL,
    ltv_ratio DECIMAL(5,4) NOT NULL,
    cmhc_required BOOLEAN NOT NULL,
    cmhc_premium_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    qualifying_rate DECIMAL(5,4) NOT NULL,
    max_mortgage_amount DECIMAL(12,2) NOT NULL,
    stress_test_passed BOOLEAN NOT NULL,
    calculation_breakdown JSONB NOT NULL,
    decline_reason_count INTEGER NOT NULL DEFAULT 0,
    condition_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by VARCHAR(50) NOT NULL,
    overridden_at TIMESTAMPTZ,
    overridden_by VARCHAR(50)
);

CREATE INDEX ix_underwriting_evaluations_application_id ON underwriting_evaluations(application_id);
CREATE INDEX ix_underwriting_evaluations_status ON underwriting_evaluations(status);
CREATE INDEX ix_underwriting_evaluations_decision ON underwriting_evaluations(decision);
CREATE INDEX ix_underwriting_evaluations_ltv ON underwriting_evaluations(ltv_ratio);
CREATE INDEX ix_underwriting_evaluations_cmhc ON underwriting_evaluations(cmhc_required);
CREATE INDEX ix_underwriting_evaluations_stress_test ON underwriting_evaluations(stress_test_passed);
CREATE INDEX ix_underwriting_evaluations_created_at ON underwriting_evaluations(created_at DESC);
CREATE INDEX ix_underwriting_evaluations_application_created ON underwriting_evaluations(application_id, created_at DESC);
CREATE INDEX ix_underwriting_evaluations_decision_ltv ON underwriting_evaluations(decision, ltv_ratio);
CREATE INDEX gin_underwriting_evaluations_breakdown ON underwriting_evaluations USING GIN(calculation_breakdown);
```

```sql
-- Create decline reasons tables
CREATE TABLE underwriting_decline_reasons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reason_code VARCHAR(50) UNIQUE NOT NULL,
    reason_text TEXT NOT NULL,
    priority INTEGER UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE evaluation_decline_reasons (
    evaluation_id UUID NOT NULL REFERENCES underwriting_evaluations(id) ON DELETE CASCADE,
    decline_reason_id UUID NOT NULL REFERENCES underwriting_decline_reasons(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (evaluation_id, decline_reason_id)
);

CREATE INDEX ix_evaluation_decline_reasons_eval ON evaluation_decline_reasons(evaluation_id, created_at);
```

```sql
-- Create conditions tables
CREATE TABLE underwriting_conditions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    condition_code VARCHAR(50) UNIQUE NOT NULL,
    condition_text TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE evaluation_conditions (
    evaluation_id UUID NOT NULL REFERENCES underwriting_evaluations(id) ON DELETE CASCADE,
    condition_id UUID NOT NULL REFERENCES underwriting_conditions(id),
    is_waived BOOLEAN NOT NULL DEFAULT false,
    waived_by VARCHAR(50),
    waived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (evaluation_id, condition_id)
);
```

```sql
-- Create override audit table
CREATE TABLE underwriting_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES underwriting_evaluations(id) ON DELETE RESTRICT,
    original_decision VARCHAR(20) NOT NULL,
    new_decision VARCHAR(20) NOT NULL,
    override_reason TEXT NOT NULL,
    bypassed_conditions JSONB NOT NULL DEFAULT '[]',
    overridden_by VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_underwriting_overrides_evaluation ON underwriting_overrides(evaluation_id, created_at DESC);
```

### 4.2 Data Migration
```sql
-- Seed decline reasons
INSERT INTO underwriting_decline_reasons (reason_code, reason_text, priority) VALUES
('LTV_EXCEEDS_MAXIMUM', 'Loan-to-value ratio exceeds 95% maximum', 1),
('GDS_EXCEEDS_THRESHOLD', 'GDS ratio exceeds 39% OSFI B-20 limit', 2),
('TDS_EXCEEDS_THRESHOLD', 'TDS ratio exceeds 44% OSFI B-20 limit', 3),
('STRESS_TEST_FAILED', 'Fails OSFI B-20 stress test at qualifying rate', 4),
('INSUFFICIENT_DOWN_PAYMENT', 'Down payment below CMHC minimum requirements', 5),
('UNVERIFIED_RENTAL_INCOME', 'Rental income verification required', 6),
('SELF_EMPLOYED_INCOME_UNVERIFIED', 'Self-employed income verification required', 7);

-- Seed conditions
INSERT INTO underwriting_conditions (condition_code, condition_text) VALUES
('SELF_EMPLOYED_INCOME_VERIFICATION', 'Provide 2 years Notice of Assessment and accountant letter'),
('RENTAL_INCOME_VERIFICATION', 'Provide executed lease and 3 months bank statements'),
('ADDITIONAL_PROPERTY_DEBT_VERIFICATION', 'Disclose all mortgages and property taxes for other properties'),
('APPRAISAL_REQUIRED', 'Full appraisal required for subject property'),
('DOWN_PAYMENT_SOURCE_VERIFICATION', '90-day history of down payment source funds');
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Stress Test Enforcement**: All calculations MUST use `qualifying_rate = max(contract_rate + 2%, 5.25%)`
- **Ratio Limits**: Hard caps enforced at GDS 39%, TDS 44% - cannot be configured per application
- **Audit Trail**: `calculation_breakdown` JSON must contain:
  ```json
  {
    "pith_amount": 2456.78,
    "qualifying_rate_used": 0.0725,
    "stress_test_threshold": 0.0525,
    "gds_numerator": 3123.45,
    "tds_numerator": 4234.56,
    "income_used": 8000.00,
    "ltv_calculation": "450000/500000",
    "cmhc_tier_applied": "85.01-90%",
    "timestamp": "2024-01-15T14:30:00Z"
  }
  ```
- **Logging**: Every evaluation must log `decision`, `gds_ratio`, `tds_ratio`, `ltv_ratio`, `stress_test_passed` with `correlation_id` - **NEVER log income values or debt details**

### 5.2 FINTRAC Compliance
- **Immutable Records**: `underwriting_evaluations` table rows are never updated after creation. Overrides create new rows in `underwriting_overrides` table.
- **Transaction Flagging**: If `loan_amount >= 10000`, evaluation must set `is_large_transaction = true` (add column if needed) for downstream FINTRAC reporting
- **5-Year Retention**: All tables must have `created_at` indexed for retention policy enforcement
- **Identity Verification Logging**: When evaluation includes identity verification results, log only verification status (pass/fail) and timestamp - **never log SIN/DOB**

### 5.3 CMHC Insurance Rules
- **LTV Precision**: Use `DECIMAL(5,4)` for LTV to prevent precision loss in tier calculations
- **Premium Calculation**: Apply premium to *base loan amount only*, not including premium itself (no stacking)
- **Tier Boundaries**: Inclusive of lower bound, exclusive of upper bound:
  - `80.01% <= LTV <= 85.00%` → 2.80%
  - `85.01% <= LTV <= 90.00%` → 3.10%
  - `90.01% <= LTV <= 95.00%` → 4.00%
- **Down Payment Tiers**: Enforce CMHC minimums:
  - ≤$500k: 5% minimum
  - $500k-$1.5M: 5% of first $500k + 10% of remainder
  - >$1.5M: 20% minimum (CMHC not available)

### 5.4 PIPEDA Data Handling
- **No PII in Logs**: **NEVER** log `gross_monthly_income`, `monthly_property_tax`, debt balances, or any applicant-identifying information
- **Encrypted Fields**: If storing applicant PII (SIN, DOB) in related tables, must use `encrypt_pii()` from `common.security` - **this module must not contain raw PII fields**
- **Hashed Lookups**: Use SHA256 hash of SIN for any cross-reference queries: `sin_hash = hashlib.sha256(sin.encode()).hexdigest()`
- **Data Minimization**: Only store financial ratios and calculation metadata - income values remain in originating application module

### 5.5 Authentication & Authorization
| Endpoint | Required Scope | Role |
|----------|----------------|------|
| `POST /calculate` | `underwriting:calculate` | Underwriter, Broker |
| `POST /evaluate` | `underwriting:evaluate` | Underwriter |
| `GET /result` | `underwriting:read` | Underwriter, Auditor |
| `POST /override` | `underwriting:override` | Admin, Chief Underwriter |

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy
```python
# In modules/underwriting/exceptions.py
class UnderwritingException(AppException):
    """Base exception for underwriting module"""
    pass

class UnderwritingNotFoundError(UnderwritingException):
    """Resource not found"""
    pass

class UnderwritingValidationError(UnderwritingException):
    """Input validation failure"""
    pass

class UnderwritingBusinessRuleError(UnderwritingException):
    """Business rule violation"""
    pass

class UnderwritingOverrideError(UnderwritingException):
    """Override operation not permitted"""
    pass
```

### Error Code Mapping

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `UnderwritingNotFoundError` | 404 | `UNDERWRITING_001` | "{Resource} not found: {id}" | Application ID not found |
| `UnderwritingValidationError` | 422 | `UNDERWRITING_002` | "{field}: {reason}" | Negative property value |
| `UnderwritingBusinessRuleError` | 409 | `UNDERWRITING_003` | "Business rule violated: {rule}" | LTV > 95% |
| `InvalidCalculationError` | 400 | `UNDERWRITING_004` | "Invalid calculation parameters: {detail}" | Missing required field |
| `IncompleteApplicationError` | 400 | `UNDERWRITING_005` | "Application data incomplete: {missing}" | No income data |
| `OverrideValidationError` | 400 | `UNDERWRITING_006` | "Override reason must be >= 20 characters" | Short reason |
| `AuthorizationError` | 403 | `AUTH_007` | "Admin privileges required" | Non-admin override |
| `OverrideNotAllowedError` | 409 | `UNDERWRITING_008` | "Override not allowed on {decision}" | Overriding DECLINED |
| `EvaluationExistsError` | 409 | `UNDERWRITING_009` | "Evaluation already exists for application {id}" | Duplicate evaluate |

### Structured Error Response Format
All errors return:
```json
{
  "detail": "Human-readable message",
  "error_code": "UNDERWRITING_XXX",
  "correlation_id": "uuid-from-request",
  "timestamp": "2024-01-15T14:30:00Z",
  "context": {
    "application_id": "optional-uuid",
    "field": "optional-field-name"
  }
}
```

---

## 7. Testing Requirements

### Unit Tests (pytest.mark.unit)
- Test each calculation algorithm in isolation with boundary values
- Test LTV tier edge cases (80.01%, 85.00%, 85.01%)
- Test stress test rate selection logic
- Test decision tree with all decline reason combinations
- Test CMHC premium calculations

### Integration Tests (pytest.mark.integration)
- Full end-to-end evaluation flow
- Concurrent evaluation of same application (conflict handling)
- Override workflow with audit trail verification
- Database transaction rollback on calculation failure
- Query performance with 1M+ evaluation records

### Compliance Tests
- Verify no PII in logs (structlog capture assertion)
- Verify calculation_breakdown JSON structure for OSFI audit
- Verify 5-year retention query performance
- Verify immutable record enforcement (attempted update fails)

---

## 8. Performance & Scalability

### Query Optimization
- Use `SELECT ... FOR UPDATE SKIP LOCKED` for processing queue if needed
- Materialized view for daily underwriting metrics: `underwriting_metrics_mv`
- Partition `underwriting_evaluations` by `created_at` (monthly) for retention policy

### Caching Strategy
- Cache `underwriting_decline_reasons` and `underwriting_conditions` in service startup
- Do not cache evaluation results (regulatory requirement for real-time calculations)

### Rate Limiting
- `POST /calculate`: 100 requests/minute per user
- `POST /evaluate`: 10 requests/minute per user
- `POST /override`: 5 requests/minute per admin

---

## 9. Future Considerations (Warning Comments)

```python
# WARNING: Self-employed income calculation rules not yet defined
# TODO: Implement T2125 analysis and 2-year average income rules
# WARNING: Rental income treatment (add-back percentage) not finalized
# TODO: Define % of rental income allowed based on lease term verification
# WARNING: Multi-property debt aggregation strategy pending
# TODO: Design debt-service aggregation for borrowers with >3 properties
# WARNING: Conditional approval criteria priority ranking not specified
# TODO: Define which conditions block approval vs. post-closing requirements
```

---

**Design Approval Required**: Chief Underwriter, Compliance Officer, Security Architect  
**Implementation Order**: Models → Migrations → Services → Routes → Tests → Security Review