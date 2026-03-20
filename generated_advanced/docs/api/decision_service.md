# Documentation Output

Here are the generated documentation files for the **Decision Service** module.

---

## 1. API Documentation

**File:** `docs/api/decision_service.md`

```markdown
# Decision Service API

## Overview
The Decision Service provides a deterministic rule engine for evaluating mortgage underwriting applications. It enforces OSFI B-20 guidelines, CMHC insurance requirements, and standard risk thresholds.

## POST /api/v1/decision/evaluate

Evaluates a mortgage application against underwriting policy rules.

**Request:**
```json
{
  "application_id": "uuid-v4",
  "loan_amount": "450000.00",
  "property_value": "500000.00",
  "gross_monthly_income": "12000.00",
  "contract_rate": "4.50",
  "piti": "2800.00",
  "other_debts": "500.00",
  "is_insured": false
}
```

**Response (200 OK):**
```json
{
  "application_id": "uuid-v4",
  "decision": "APPROVED",
  "qualifying_rate": "6.50",
  "calculated_ratios": {
    "gds": "23.33",
    "tds": "27.50",
    "ltv": "90.00"
  },
  "insurance_required": true,
  "insurance_premium_rate": "2.80",
  "stress_test_passed": true,
  "evaluated_at": "2026-03-02T14:30:00Z"
}
```

**Response (200 OK - Rejected):**
```json
{
  "application_id": "uuid-v4",
  "decision": "REJECTED",
  "qualifying_rate": "6.50",
  "calculated_ratios": {
    "gds": "42.00",
    "tds": "48.00",
    "ltv": "90.00"
  },
  "rejection_reasons": [
    "GDS ratio 42.00% exceeds maximum limit of 39.00%",
    "TDS ratio 48.00% exceeds maximum limit of 44.00%"
  ],
  "evaluated_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- **400 Bad Request:** Invalid input data or malformed financial values.
  ```json
  {
    "detail": "Gross monthly income must be positive",
    "error_code": "INVALID_INPUT"
  }
  ```
- **422 Unprocessable Entity:** Pydantic validation failed.
  ```json
  {
    "detail": [
      {
        "loc": ["body", "loan_amount"],
        "msg": "field required",
        "type": "value_error.missing"
      }
    ],
    "error_code": "VALIDATION_ERROR"
  }
  ```
- **401 Unauthorized:** Missing or invalid authentication token.
- **500 Internal Server Error:** Unexpected system failure.

**Permissions:**
- `underwriting:write` (Required to submit evaluation)
```

---

## 2. Module README

**File:** `docs/modules/decision_service.md`

```markdown
# Decision Service Module

## Overview
The Decision Service acts as the central brain of the mortgage underwriting system. It is a pure, deterministic rule engine that takes normalized borrower financial data and applies regulatory and institutional policies to render a final underwriting decision.

### Key Responsibilities
- **Rule Application:** Executes a series of logical checks against borrower data.
- **Regulatory Compliance:** Enforces OSFI B-20 stress tests and ratio limits.
- **Insurance Logic:** Determines CMHC insurance requirements and premium tiers based on LTV.
- **Auditability:** All decisions and intermediate calculations are logged for FINTRAC compliance.

## Core Calculations

All monetary values use `Decimal` to prevent floating-point precision loss.

### 1. Stress Test (OSFI B-20)
Determines the minimum interest rate used to qualify the borrower.
```python
qualifying_rate = max(contract_rate + 2.00%, 5.25%)
```

### 2. Gross Debt Service (GDS)
Measures the percentage of gross income used for housing costs.
- **Formula:** `(PITH / Gross Monthly Income) * 100`
- **Limit:** `39%`
- **Components:** PITH = Principal, Interest, Taxes, Heating (and 50% condo fees if applicable).

### 3. Total Debt Service (TDS)
Measures the percentage of gross income used for housing costs plus all other debts.
- **Formula:** `((PITH + Other Debts) / Gross Monthly Income) * 100`
- **Limit:** `44%`

### 4. Loan-to-Value (LTV)
Measures the mortgage amount against the property value.
- **Formula:** `(Mortgage Amount / Property Value) * 100`
- **Limits:** 
  - Insured: ≤ 95%
  - Uninsured: ≤ 80%

### 5. Insurance Premium (CMHC)
Applied automatically if LTV > 80%.
- **80.01% - 85.00%:** 2.80%
- **85.01% - 90.00%:** 3.10%
- **90.01% - 95.00%:** 4.00%

## Usage Example

```python
from modules.decision_service.services import DecisionEngine
from modules.decision_service.schemas import ApplicationInput

async def evaluate_application(data: dict):
    # 1. Validate input
    application = ApplicationInput(**data)

    # 2. Run engine
    engine = DecisionEngine()
    result = await engine.evaluate(application)

    # 3. Handle result
    if result.decision == "APPROVED":
        print(f"Approved at rate: {result.qualifying_rate}")
    else:
        print(f"Rejected: {result.rejection_reasons}")
```

## Audit & Logging
Per FINTRAC requirements:
- The `DecisionEngine` logs the full breakdown of GDS/TDS calculations using `structlog`.
- A `correlation_id` is required to trace the decision back to the specific application request.
- No PII (SIN/DOB) is logged; only hashed identifiers or application IDs are used.
```

---

## 3. Configuration Notes

**File:** `.env.example` (Append to existing file)

```bash
# ... existing config ...

# Decision Service Configuration
# Default floor rate for OSFI B-20 Stress Test (usually 5.25%)
DECISION_STRESS_TEST_FLOOR_RATE=5.25

# Hard limit overrides for GDS/TDS (WARNING: Changing these may violate OSFI B-20)
DECISION_GDS_LIMIT=39
DECISION_TDS_LIMIT=44

# Insurance Premium Thresholds (CMHC)
DECISION_INSURANCE_THRESHOLD=80.00
```

---

## 4. Changelog Update

**File:** `CHANGELOG.md` (Append to existing file)

```markdown
## [2026-03-02]
### Added
- Decision Service: New deterministic rule engine module for underwriting.
- Decision Service: Implementation of OSFI B-20 Stress Test logic (Qualifying Rate = max(contract + 2%, 5.25%)).
- Decision Service: GDS/TDS calculation endpoints with hard limits (39% / 44%).
- Decision Service: LTV calculation and CMHC insurance premium tier logic.
- Decision Service: Audit logging for all decision calculations to satisfy FINTRAC traceability.

### Changed
- Updated common/exceptions.py to include `UnderwritingCriteriaError`.

### Fixed
- N/A
```