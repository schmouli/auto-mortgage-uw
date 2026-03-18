# Underwriting Engine
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Underwriting Engine Design Plan

**Module Path**: `modules/underwriting/`  
**Feature Slug**: `underwriting-engine`  
**Regulatory Scope**: OSFI B-20, FINTRAC, CMHC, PIPEDA  

---

## 1. Endpoints

### 1.1 Run Qualification (No Save)
**POST** `/api/v1/underwriting/calculate`

**Authentication**: Authenticated (lender user)

**Request Body Schema** (`UnderwritingCalculationRequest`):
```python
{
    "application_id": str,  # optional, for context only
    "borrower_profile": {
        "gross_annual_income": Decimal,  # required, > 0
        "gross_monthly_income": Decimal,  # optional, calculated if not provided
        "employment_type": Enum["SALARIED", "SELF_EMPLOYED", "OTHER"],  # required
        "self_employed_verified_income": Decimal,  # required if employment_type == SELF_EMPLOYED
        "other_income": Decimal,  # optional, default 0
        "condo_fees_monthly": Decimal,  # optional, default 0
        "property_taxes_annual": Decimal,  # required for GDS
        "heating_costs_monthly": Decimal,  # required for GDS
        "rental_income": Decimal,  # optional, from subject property
        "rental_income_verified": bool,  # default False (50% haircut applied)
    },
    "property_details": {
        "property_value": Decimal,  # required, > 0
        "property_type": Enum["SINGLE_FAMILY", "CONDO", "MULTI_UNIT"],  # required
        "is_owner_occupied": bool,  # required
    },
    "loan_details": {
        "loan_amount": Decimal,  # required, > 0
        "contract_rate": Decimal,  # required, > 0
        "amortization_years": int,  # required, 5-30
        "payment_frequency": Enum["MONTHLY", "BI_WEEKLY", "ACCELERATED_BI_WEEKLY"],  # required
    },
    "existing_debts": List[DebtItem],  # optional
    "other_properties": List[OtherProperty],  # optional, for debt aggregation
}
```

**DebtItem**:
```python
{
    "debt_type": Enum["CREDIT_CARD", "LINE_OF_CREDIT", "AUTO_LOAN", "PERSONAL_LOAN", "OTHER_MORTGAGE"],
    "monthly_payment": Decimal,  # required, >= 0
    "outstanding_balance": Decimal,  # required, >= 0
    "is_secured": bool,  # default False
}
```

**OtherProperty**:
```python
{
    "property_id": str,  # optional reference
    "monthly_mortgage_payment": Decimal,  # required
    "outstanding_balance": Decimal,  # required
    "rental_income": Decimal,  # optional
    "is_negative_cash_flow": bool,  # calculated if rental_income < mortgage_payment
}
```

**Response Schema** (`UnderwritingCalculationResponse`):
```python
{
    "qualifies": bool,
    "decision": Enum["APPROVED", "CONDITIONAL", "DECLINED"],
    "gds_ratio": Decimal,  # rounded to 2 decimal places
    "tds_ratio": Decimal,  # rounded to 2 decimal places
    "ltv_ratio": Decimal,  # rounded to 2 decimal places
    "cmhc_required": bool,
    "cmhc_premium_amount": Decimal,  # 0 if not required
    "qualifying_rate": Decimal,  # OSFI stress test rate
    "max_mortgage": Decimal,  # maximum loan amount borrower qualifies for
    "stress_test_passed": bool,
    "decline_reasons": List[str],  # ordered by priority
    "conditions": List[str],  # for CONDITIONAL approvals
    "calculation_details": {
        "gross_monthly_income": Decimal,
        "monthly_mortgage_payment": Decimal,
        "pith_amount": Decimal,  # Principal + Interest + Taxes + Heat
        "total_monthly_debts": Decimal,
        "used_condo_fee": Decimal,  # 50% of condo fee
        "used_rental_income": Decimal,  # 50% if not verified, 100% if verified
        "down_payment_required": Decimal,  # based on property value tiers
        "ltv_calculated": Decimal,
    },
    "warnings": List[str],  # non-blocking issues (e.g., high LTV)
}
```

**Error Responses**:
- `400`: Application data incomplete or invalid (`UNDERWRITING_002`)
- `422`: Validation error in request payload (`UNDERWRITING_002`)
- `404`: Referenced application not found (`UNDERWRITING_001`)

---

### 1.2 Evaluate and Save Underwriting Decision
**POST** `/api/v1/underwriting/applications/{application_id}/evaluate`

**Authentication**: Authenticated (underwriter role required)

**Path Parameters**:
- `application_id`: str (UUID format)

**Request Body Schema**: Same as `/calculate` but `application_id` in path takes precedence

**Response Schema** (`UnderwritingResultResponse`):
```python
{
    "underwriting_result_id": str,
    "application_id": str,
    "decision": Enum["APPROVED", "CONDITIONAL", "DECLINED"],
    "decision_date": datetime,
    "underwritten_by": str,  # user_id from JWT
    "ratios": {
        "gds_ratio": Decimal,
        "tds_ratio": Decimal,
        "ltv_ratio": Decimal,
    },
    "cmhc": {
        "required": bool,
        "premium_amount": Decimal,
        "premium_rate": Decimal,  # e.g., 0.0280
    },
    "qualifying_rate": Decimal,
    "max_qualified_mortgage": Decimal,
    "decline_reasons": List[str],
    "conditions": List[str],
    "stress_test_passed": bool,
    "audit_trail": {
        "created_at": datetime,
        "calculation_snapshot": dict,  # full calculation details for audit
    }
}
```

**Error Responses**:
- `400`: Application not in correct status for evaluation (`UNDERWRITING_003`)
- `403`: User lacks underwriting authority (`UNDERWRITING_004`)
- `404`: Application not found (`UNDERWRITING_001`)
- `409`: Underwriting result already exists for this application (`UNDERWRITING_003`)

---

### 1.3 Retrieve Saved Underwriting Result
**GET** `/api/v1/underwriting/applications/{application_id}/result`

**Authentication**: Authenticated (lender or underwriter)

**Path Parameters**:
- `application_id`: str

**Response Schema**: Same as `UnderwritingResultResponse`

**Error Responses**:
- `404`: Underwriting result not found (`UNDERWRITING_001`)
- `403`: User not authorized to view this application (`UNDERWRITING_004`)

---

### 1.4 Admin Override Underwriting Decision
**POST** `/api/v1/underwriting/applications/{id}/override`

**Authentication**: Authenticated (admin role only)

**Path Parameters**:
- `id`: str (application_id)

**Request Body Schema** (`UnderwritingOverrideRequest`):
```python
{
    "original_decision": Enum["APPROVED", "CONDITIONAL", "DECLINED"],  # must match current
    "new_decision": Enum["APPROVED", "CONDITIONAL", "DECLINED"],
    "override_reason": str,  # required, min 20 chars, max 500 chars
    "justification_details": str,  # optional, additional context
    "bypassed_rules": List[str],  # e.g., ["GDS_THRESHOLD", "TDS_THRESHOLD"]
}
```

**Response Schema** (`UnderwritingOverrideResponse`):
```python
{
    "override_id": str,
    "application_id": str,
    "overridden_by": str,
    "overridden_at": datetime,
    "original_decision": str,
    "new_decision": str,
    "override_reason": str,
    "bypassed_rules": List[str],
    "audit_hash": str,  # SHA256 of override record for immutability verification
}
```

**Error Responses**:
- `400`: Cannot override to same decision or mismatched original decision (`UNDERWRITING_003`)
- `403`: User lacks admin override authority (`UNDERWRITING_004`)
- `404`: Underwriting result not found (`UNDERWRITING_001`)
- `422`: Override reason insufficient (`UNDERWRITING_002`)

---

## 2. Models & Database

### 2.1 UnderwritingResult Model
**Table**: `underwriting_results`

| Column | Type | Constraints | Index | Encrypted | Notes |
|--------|------|-------------|-------|-----------|-------|
| id | UUID | PRIMARY KEY | - | No | - |
| application_id | UUID | FOREIGN KEY (applications.id), NOT NULL | IX_underwriting_results_application_id | No | Unique per application |
| decision | VARCHAR(12) | NOT NULL, CHECK IN ('APPROVED','CONDITIONAL','DECLINED') | IX_underwriting_results_decision | No | - |
| gds_ratio | DECIMAL(5,2) | NOT NULL | - | No | Stored for audit |
| tds_ratio | DECIMAL(5,2) | NOT NULL | - | No | Stored for audit |
| ltv_ratio | DECIMAL(5,2) | NOT NULL | - | No | - |
| cmhc_required | BOOLEAN | NOT NULL, DEFAULT FALSE | - | No | - |
| cmhc_premium_amount | DECIMAL(12,2) | NOT NULL, DEFAULT 0 | - | No | - |
| cmhc_premium_rate | DECIMAL(5,4) | NOT NULL, DEFAULT 0 | - | No | e.g., 0.0280 |
| qualifying_rate | DECIMAL(5,3) | NOT NULL | - | No | OSFI stress test rate |
| max_qualified_mortgage | DECIMAL(12,2) | NOT NULL | - | No | Based on GDS/TDS limits |
| stress_test_passed | BOOLEAN | NOT NULL | - | No | - |
| decline_reasons | JSONB | NOT NULL, DEFAULT '[]' | GIN index | No | Array of reason codes |
| conditions | JSONB | NOT NULL, DEFAULT '[]' | GIN index | No | Array of condition texts |
| calculation_snapshot | JSONB | NOT NULL | - | No | Full audit trail of inputs/outputs |
| underwritten_by | VARCHAR(50) | NOT NULL | IX_underwriting_results_underwritten_by | No | User ID from JWT |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | IX_underwriting_results_created_at | No | FINTRAC audit |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | - | No | Auto-updated |

**Indexes**:
- `IX_underwriting_results_application_id` (UNIQUE)
- `IX_underwriting_results_decision`
- `IX_underwriting_results_underwritten_by`
- `IX_underwriting_results_created_at`
- GIN index on `decline_reasons` and `conditions`

---

### 2.2 UnderwritingOverride Model
**Table**: `underwriting_overrides`

| Column | Type | Constraints | Index | Encrypted | Notes |
|--------|------|-------------|-------|-----------|-------|
| id | UUID | PRIMARY KEY | - | No | - |
| application_id | UUID | FOREIGN KEY (applications.id), NOT NULL | IX_underwriting_overrides_application_id | No | - |
| underwriting_result_id | UUID | FOREIGN KEY (underwriting_results.id), NOT NULL | IX_underwriting_overrides_result_id | No | - |
| original_decision | VARCHAR(12) | NOT NULL | - | No | - |
| new_decision | VARCHAR(12) | NOT NULL | - | No | - |
| override_reason | TEXT | NOT NULL | - | No | FINTRAC audit trail |
| justification_details | TEXT | - | - | No | Optional |
| bypassed_rules | JSONB | NOT NULL, DEFAULT '[]' | GIN index | No | e.g., ["GDS_THRESHOLD"] |
| overridden_by | VARCHAR(50) | NOT NULL | IX_underwriting_overrides_overridden_by | No | User ID |
| override_hash | VARCHAR(64) | NOT NULL | UNIQUE | No | SHA256 for immutability |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | IX_underwriting_overrides_created_at | No | FINTRAC: immutable |

**Indexes**:
- `IX_underwriting_overrides_application_id`
- `IX_underwriting_overrides_result_id`
- `IX_underwriting_overrides_overridden_by`
- `IX_underwriting_overrides_created_at`
- GIN index on `bypassed_rules`

---

### 2.3 UnderwritingDebt Model
**Table**: `underwriting_debts`

| Column | Type | Constraints | Index | Notes |
|--------|------|-------------|-------|-------|
| id | UUID | PRIMARY KEY | - | - |
| application_id | UUID | FOREIGN KEY (applications.id), NOT NULL | IX_underwriting_debts_application_id | Part of TDS calculation |
| debt_type | VARCHAR(30) | NOT NULL, CHECK IN (enum) | IX_underwriting_debts_debt_type | - |
| monthly_payment | DECIMAL(10,2) | NOT NULL, >= 0 | - | - |
| outstanding_balance | DECIMAL(12,2) | NOT NULL, >= 0 | - | For LTV adjustments |
| is_secured | BOOLEAN | NOT NULL, DEFAULT FALSE | - | Affects risk weighting |
| is_property_related | BOOLEAN | NOT NULL, DEFAULT FALSE | IX_underwriting_debts_property_flag | True if other mortgage |
| property_id | UUID | FOREIGN KEY (properties.id), NULLABLE | - | For multi-property aggregation |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | - | FINTRAC audit |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | - | - |

**Indexes**:
- Composite: `IX_underwriting_debts_application_id_property_flag` (for TDS queries)

---

## 3. Business Logic

### 3.1 Core Algorithms

#### Stress Test Rate (OSFI B-20)
```python
qualifying_rate = max(contract_rate + 0.02, Decimal('5.25'))
```
- **Precision**: 3 decimal places
- **Logging**: Must log `contract_rate`, `calculated_rate`, and `final_qualifying_rate` with correlation_id

#### GDS Calculation
```python
pith = monthly_mortgage_payment + (property_taxes_annual / 12) + heating_costs_monthly
if property_type == "CONDO":
    pith += condo_fees_monthly * Decimal('0.50')  # 50% of condo fees

gross_monthly_income = verified_gross_monthly_income
if rental_income:
    gross_monthly_income += rental_income * (Decimal('1.0') if rental_income_verified else Decimal('0.50'))

gds_ratio = pith / gross_monthly_income
```
- **Threshold**: gds_ratio ≤ 39%
- **Precision**: 2 decimal places

#### TDS Calculation
```python
total_debt_service = pith  # from GDS calculation

# Add all debt obligations
for debt in existing_debts:
    if debt.debt_type == "CREDIT_CARD":
        # Use 3% of balance if no payment reported
        total_debt_service += debt.monthly_payment or (debt.outstanding_balance * Decimal('0.03'))
    else:
        total_debt_service += debt.monthly_payment

# Multi-property debt aggregation
for prop in other_properties:
    total_debt_service += prop.monthly_mortgage_payment
    if prop.rental_income:
        # Offset: use rental income (50% if not verified)
        rental_offset = prop.rental_income * (Decimal('0.50') if not prop.rental_income_verified else Decimal('1.0'))
        total_debt_service -= min(rental_offset, prop.monthly_mortgage_payment)

tds_ratio = total_debt_service / gross_monthly_income
```
- **Threshold**: tds_ratio ≤ 44%
- **Precision**: 2 decimal places

#### LTV & Down Payment Rules (CMHC)
```python
ltv_ratio = loan_amount / property_value

# Down payment requirements
if property_value <= Decimal('500000'):
    min_down_payment = property_value * Decimal('0.05')
elif property_value <= Decimal('1500000'):
    min_down_payment = (Decimal('500000') * Decimal('0.05')) + ((property_value - Decimal('500000')) * Decimal('0.10'))
else:
    min_down_payment = property_value * Decimal('0.20')

# CMHC Insurance
if ltv_ratio > Decimal('0.80'):
    cmhc_required = True
    if Decimal('0.8001') <= ltv_ratio <= Decimal('0.85'):
        cmhc_premium_rate = Decimal('0.0280')
    elif Decimal('0.8501') <= ltv_ratio <= Decimal('0.90'):
        cmhc_premium_rate = Decimal('0.0310')
    elif Decimal('0.9001') <= ltv_ratio <= Decimal('0.95'):
        cmhc_premium_rate = Decimal('0.0400')
    else:
        cmhc_premium_rate = Decimal('0.0000')  # >95% not eligible
    cmhc_premium_amount = loan_amount * cmhc_premium_rate
else:
    cmhc_required = False
    cmhc_premium_rate = Decimal('0.0000')
    cmhc_premium_amount = Decimal('0.00')
```

#### Max Mortgage Calculation
```python
# Based on GDS limit
max_payment_gds = gross_monthly_income * Decimal('0.39') - (property_taxes_annual / 12) - heating_costs_monthly
if property_type == "CONDO":
    max_payment_gds -= condo_fees_monthly * Decimal('0.50')

# Based on TDS limit
max_payment_tds = gross_monthly_income * Decimal('0.44') - total_other_debts - (property_taxes_annual / 12) - heating_costs_monthly
if property_type == "CONDO":
    max_payment_tds -= condo_fees_monthly * Decimal('0.50')

max_affordable_payment = min(max_payment_gds, max_payment_tds)
max_mortgage = calculate_present_value(max_affordable_payment, qualifying_rate, amortization_years)
```

### 3.2 Decision Tree

```python
def determine_decision(gds_ratio, tds_ratio, ltv_ratio, stress_test_passed, cmhc_eligible):
    decline_reasons = []
    conditions = []

    # Hard declines (no override)
    if not stress_test_passed:
        decline_reasons.append("STRESS_TEST_FAILED")
    
    if ltv_ratio > Decimal('0.95'):
        decline_reasons.append("LTV_EXCEEDS_MAXIMUM")
    
    if gds_ratio > Decimal('0.39'):
        decline_reasons.append("GDS_EXCEEDS_THRESHOLD")
    
    if tds_ratio > Decimal('0.44'):
        decline_reasons.append("TDS_EXCEEDS_THRESHOLD")

    # Conditional approval criteria
    if gds_ratio > Decimal('0.35') and gds_ratio <= Decimal('0.39'):
        conditions.append("HIGH_GDS_WARNING")
    
    if tds_ratio > Decimal('0.40') and tds_ratio <= Decimal('0.44'):
        conditions.append("HIGH_TDS_WARNING")
    
    if ltv_ratio > Decimal('0.90'):
        conditions.append("HIGH_LTV_REQUIREMENTS")
    
    if cmhc_required and not cmhc_eligible:
        decline_reasons.append("CMHC_INELIGIBLE_HIGH_LTV")

    # Self-employed specific conditions
    if employment_type == "SELF_EMPLOYED" and self_employed_verified_income < gross_annual_income:
        conditions.append("SELF_EMPLOYED_INCOME_VERIFICATION_REQUIRED")

    # Multi-property conditions
    if len(other_properties) > 1:
        conditions.append("MULTI_PROPERTY_DEBT_SERVICE_VERIFICATION")

    # Final decision
    if decline_reasons:
        return ("DECLINED", decline_reasons, [])
    elif conditions:
        return ("CONDITIONAL", [], conditions)
    else:
        return ("APPROVED", [], [])
```

### 3.3 State Machine (Application Status)

Application status transitions managed by underwriting service:

```
DRAFT → SUBMITTED → UNDER_REVIEW → 
    ├→ APPROVED → COMPLETED
    ├→ CONDITIONAL → (conditions met) → APPROVED → COMPLETED
    └→ DECLINED → (override) → APPROVED/CONDITIONAL
```

**Rules**:
- Only `UNDER_REVIEW` status can be evaluated
- `DECLINED` applications cannot be re-evaluated without override
- `CONDITIONAL` requires manual review of conditions before final approval

### 3.4 Validation Rules with Thresholds

| Rule | Threshold | Action | Error Code |
|------|-----------|--------|------------|
| Gross Monthly Income | > 0 | Hard stop | UNDERWRITING_002 |
| Property Value | ≥ $50,000 | Hard stop | UNDERWRITING_002 |
| Loan Amount | ≥ $10,000 | Hard stop | UNDERWRITING_002 |
| Contract Rate | 1% - 15% | Hard stop | UNDERWRITING_002 |
| Amortization | 5-30 years | Hard stop | UNDERWRITING_002 |
| GDS Ratio | ≤ 39% | Decline if > 39% | UNDERWRITING_003 |
| TDS Ratio | ≤ 44% | Decline if > 44% | UNDERWRITING_003 |
| LTV Ratio | ≤ 95% | Decline if > 95% | UNDERWRITING_003 |
| Down Payment | Min by tier | Decline if insufficient | UNDERWRITING_003 |

---

## 4. Migrations

### 4.1 New Tables

**Migration ID**: `202401150001_create_underwriting_tables.py`

```python
# Create underwriting_results table
op.create_table(
    'underwriting_results',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('application_id', sa.UUID(), nullable=False),
    sa.Column('decision', sa.String(12), nullable=False),
    sa.Column('gds_ratio', sa.DECIMAL(5,2), nullable=False),
    sa.Column('tds_ratio', sa.DECIMAL(5,2), nullable=False),
    sa.Column('ltv_ratio', sa.DECIMAL(5,2), nullable=False),
    sa.Column('cmhc_required', sa.Boolean(), nullable=False),
    sa.Column('cmhc_premium_amount', sa.DECIMAL(12,2), nullable=False),
    sa.Column('cmhc_premium_rate', sa.DECIMAL(5,4), nullable=False),
    sa.Column('qualifying_rate', sa.DECIMAL(5,3), nullable=False),
    sa.Column('max_qualified_mortgage', sa.DECIMAL(12,2), nullable=False),
    sa.Column('stress_test_passed', sa.Boolean(), nullable=False),
    sa.Column('decline_reasons', sa.JSONB(), nullable=False),
    sa.Column('conditions', sa.JSONB(), nullable=False),
    sa.Column('calculation_snapshot', sa.JSONB(), nullable=False),
    sa.Column('underwritten_by', sa.String(50), nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(), nullable=False),
    sa.Column('updated_at', sa.TIMESTAMP(), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('application_id')
)

# Create underwriting_overrides table
op.create_table(
    'underwriting_overrides',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('application_id', sa.UUID(), nullable=False),
    sa.Column('underwriting_result_id', sa.UUID(), nullable=False),
    sa.Column('original_decision', sa.String(12), nullable=False),
    sa.Column('new_decision', sa.String(12), nullable=False),
    sa.Column('override_reason', sa.Text(), nullable=False),
    sa.Column('justification_details', sa.Text(), nullable=True),
    sa.Column('bypassed_rules', sa.JSONB(), nullable=False),
    sa.Column('overridden_by', sa.String(50), nullable=False),
    sa.Column('override_hash', sa.String(64), nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id']),
    sa.ForeignKeyConstraint(['underwriting_result_id'], ['underwriting_results.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('override_hash')
)

# Create underwriting_debts table
op.create_table(
    'underwriting_debts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('application_id', sa.UUID(), nullable=False),
    sa.Column('debt_type', sa.String(30), nullable=False),
    sa.Column('monthly_payment', sa.DECIMAL(10,2), nullable=False),
    sa.Column('outstanding_balance', sa.DECIMAL(12,2), nullable=False),
    sa.Column('is_secured', sa.Boolean(), nullable=False),
    sa.Column('is_property_related', sa.Boolean(), nullable=False),
    sa.Column('property_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(), nullable=False),
    sa.Column('updated_at', sa.TIMESTAMP(), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id']),
    sa.ForeignKeyConstraint(['property_id'], ['properties.id']),
    sa.PrimaryKeyConstraint('id')
)
```

### 4.2 Indexes
```python
# Composite index for multi-property debt queries
op.create_index(
    'ix_underwriting_debts_app_property',
    'underwriting_debts',
    ['application_id', 'is_property_related']
)

# GIN indexes for JSONB arrays
op.create_index(
    'gin_underwriting_results_decline_reasons',
    'underwriting_results',
    ['decline_reasons'],
    postgresql_using='gin'
)

op.create_index(
    'gin_underwriting_overrides_bypassed_rules',
    'underwriting_overrides',
    ['bypassed_rules'],
    postgresql_using='gin'
)
```

### 4.3 Data Migration
- **None required** for new tables
- **Future**: Backfill `underwriting_debts` from existing `liabilities` table if migrating from legacy system

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Stress Test**: Implemented in `services.py::calculate_qualifying_rate()` - **MANDATORY** for every calculation
- **Ratio Limits**: Hard-coded limits (GDS 39%, TDS 44%) enforced in `services.py::validate_ratios()`
- **Auditability**: Every calculation stores full `calculation_snapshot` JSON in `underwriting_results` table
- **Logging**: structlog must emit:
  ```json
  {
    "event": "underwriting_calculation_completed",
    "correlation_id": "...",
    "application_id": "...",
    "gds_ratio": "0.38",
    "tds_ratio": "0.42",
    "ltv_ratio": "0.85",
    "qualifying_rate": "6.250",
    "stress_test_passed": true,
    "decision": "CONDITIONAL"
  }
  ```
  **NEVER log income amounts, SIN, or DOB**.

### 5.2 FINTRAC Compliance
- **Immutable Records**: `underwriting_results` and `underwriting_overrides` tables have **NO UPDATE/DELETE** operations in codebase
- **5-Year Retention**: Records retained via PostgreSQL partition policy (monthly partitions, archived after 5 years)
- **Audit Trail**: `created_at`, `underwritten_by`, `overridden_by` track all actions
- **Transaction Flag**: Applications > CAD $10,000 auto-flagged in `applications` table (`large_transaction_flag = True`)
- **Override Hash**: SHA256 hash of override record computed on insert for tamper detection

### 5.3 CMHC Insurance Rules
- **LTV Calculation**: `loan_amount / property_value` using Decimal with 4 decimal precision
- **Premium Tiers**: Lookup table in `config.py` as `CMHC_PREMIUM_TIERS`
- **Self-Employed**: If LTV > 80% and employment_type == SELF_EMPLOYED, require additional verification (flag in conditions)

### 5.4 PIPEDA Data Handling
- **No PII in Logs**: Income values, SIN, DOB **MUST NOT** appear in structlog entries
- **Encrypted Fields**: SIN/DOB from `applications` module accessed only via `security.encrypt_pii()` and `security.decrypt_pii()`
- **Hash Lookups**: SIN lookups use SHA256 hash (`security.hash_sin()`) for `applications.sin_hash` column
- **Data Minimization**: Underwriting module only receives income **aggregates**, not source documents
- **Error Messages**: Validation errors **never** include actual income values

### 5.5 Authentication & Authorization
| Endpoint | Required Scope | Role | Notes |
|----------|----------------|------|-------|
| POST /calculate | `underwriting:read` | Lender, Underwriter | No data persistence |
| POST /evaluate | `underwriting:write` | Underwriter only | Creates immutable record |
| GET /result | `underwriting:read` | Lender, Underwriter | - |
| POST /override | `underwriting:admin` | Admin only | Requires MFA verification |

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy
```python
# modules/underwriting/exceptions.py
from common.exceptions import AppException

class UnderwritingError(AppException):
    """Base class for underwriting module errors"""
    module_code = "UNDERWRITING"

class UnderwritingNotFoundError(UnderwritingError):
    """Resource not found"""
    http_status = 404
    error_code = "UNDERWRITING_001"

class UnderwritingValidationError(UnderwritingError):
    """Input validation failed"""
    http_status = 422
    error_code = "UNDERWRITING_002"

class UnderwritingBusinessRuleError(UnderwritingError):
    """Business rule violation (e.g., ratios exceeded)"""
    http_status = 409
    error_code = "UNDERWRITING_003"

class UnderwritingOverrideUnauthorizedError(UnderwritingError):
    """User lacks override authority"""
    http_status = 403
    error_code = "UNDERWRITING_004"

class UnderwritingCalculationError(UnderwritingError):
    """Internal calculation error"""
    http_status = 500
    error_code = "UNDERWRITING_005"
```

### 6.2 Error Response Mapping

| Exception Class | HTTP Status | Error Code | Message Pattern | Example |
|-----------------|-------------|------------|-----------------|---------|
| `UnderwritingNotFoundError` | 404 | UNDERWRITING_001 | "{resource} not found: {id}" | "Underwriting result not found: app_123" |
| `UnderwritingValidationError` | 422 | UNDERWRITING_002 | "{field}: {reason}" | "gross_annual_income: must be positive Decimal" |
| `UnderwritingBusinessRuleError` | 409 | UNDERWRITING_003 | "{rule} violated: {detail}" | "GDS threshold violated: 0.42 > 0.39" |
| `UnderwritingOverrideUnauthorizedError` | 403 | UNDERWRITING_004 | "Override authority required: {user_role}" | "Override authority required: lender" |
| `UnderwritingCalculationError` | 500 | UNDERWRITING_005 | "Calculation failed: {error}" | "Calculation failed: Division by zero in LTV" |

### 6.3 Structured Error Response Format
All errors return:
```json
{
    "detail": "Human-readable message",
    "error_code": "UNDERWRITING_XXX",
    "module": "underwriting",
    "timestamp": "2024-01-15T14:30:00Z",
    "correlation_id": "req-1234567890"
}
```

### 6.4 Decline Reason Templates (Priority Order)
```python
DECLINE_REASONS = {
    "STRESS_TEST_FAILED": "Application failed OSFI B-20 stress test at {qualifying_rate}%",
    "GDS_EXCEEDS_THRESHOLD": "GDS ratio {gds_ratio} exceeds 39% limit",
    "TDS_EXCEEDS_THRESHOLD": "TDS ratio {tds_ratio} exceeds 44% limit",
    "LTV_EXCEEDS_MAXIMUM": "LTV ratio {ltv_ratio} exceeds maximum 95%",
    "INSUFFICIENT_DOWN_PAYMENT": "Down payment does not meet CMHC tier requirements",
    "CMHC_INELIGIBLE_HIGH_LTV": "LTV >80% requires CMHC insurance but borrower is ineligible",
    "UNVERIFIED_INCOME_SELF_EMPLOYED": "Self-employed income insufficiently verified for LTV >80%",
    "MULTI_PROPERTY_CASH_FLOW_NEGATIVE": "Negative cash flow on other properties exceeds tolerance",
}
```

### 6.5 Conditional Approval Conditions
```python
CONDITIONS = {
    "HIGH_GDS_WARNING": "GDS ratio >35% requires branch manager sign-off",
    "HIGH_TDS_WARNING": "TDS ratio >40% requires enhanced monitoring",
    "HIGH_LTV_REQUIREMENTS": "LTV >90% requires proof of 1.5% property tax reserve",
    "SELF_EMPLOYED_INCOME_VERIFICATION_REQUIRED": "Provide 2 years NOA and accountant letter",
    "MULTI_PROPERTY_DEBT_SERVICE_VERIFICATION": "Provide leases and mortgage statements for all properties",
    "RENTAL_INCOME_VERIFICATION": "Provide T776 and lease agreements for rental income claimed",
}
```

---

**Design Document Location**: `docs/design/underwriting-engine.md`  
**Next Steps**: Implementation of `services.py` with async methods for each algorithm, `schemas.py` with Pydantic v2 models, and `routes.py` with FastAPI routers.