Here is the documentation for the Decision Service module.

### 1. API Documentation
**File:** `docs/api/decision_service.md`

```markdown
# Decision Service API

## POST /api/v1/decision/evaluate

Evaluates a mortgage application against OSFI B-20 and CMHC guidelines to produce an underwriting decision. This endpoint acts as a pure deterministic rule engine, taking borrower and property financials to calculate ratios and determine eligibility.

**Request:**
```json
{
  "loan_amount": "450000.00",
  "property_value": "500000.00",
  "contract_rate": "4.50",
  "annual_income": "120000.00",
  "monthly_property_tax": "300.00",
  "monthly_heating": "150.00",
  "monthly_condo_fees": "0.00",
  "monthly_debt_payments": "500.00"
}
```

**Response (200):**
```json
{
  "decision": "APPROVED",
  "qualifying_rate": "6.50",
  "gds_ratio": "28.50",
  "tds_ratio": "33.00",
  "ltv_ratio": "90.00",
  "insurance_required": true,
  "insurance_premium_rate": "3.10",
  "stress_test_passed": true,
  "evaluated_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- `400`: Invalid financial input (e.g., negative values).
- `422`: Validation error (missing required fields or data type mismatch).
- `500`: Internal calculation error.

---
```

### 2. Module README
**File:** `docs/modules/decision_service.md`

```markdown
# Decision Service Module

## Overview
The Decision Service is the core rule engine for the Canadian Mortgage Underwriting System. It is responsible for applying deterministic business logic to borrower and property data to generate an underwriting decision (Approved, Referred, or Declined).

This module enforces regulatory compliance with OSFI B-20 (stress testing and ratio limits) and CMHC (insurance premium logic).

## Key Functions

### 1. Stress Testing (OSFI B-20)
Calculates the qualifying rate used to determine mortgage affordability.
- **Logic:** `qualifying_rate = max(contract_rate + 2%, 5.25%)`
- **Purpose:** Ensures the borrower can afford payments if interest rates rise.

### 2. Ratio Calculations
Determines the borrower's debt service ratios.

- **GDS (Gross Debt Service):**
  - Formula: `(Monthly Principal + Interest + Taxes + Heating) / Gross Monthly Income * 100`
  - Limit: ≤ 39%
  
- **TDS (Total Debt Service):**
  - Formula: `(Monthly PITH + Other Debt Payments) / Gross Monthly Income * 100`
  - Limit: ≤ 44%

### 3. LTV & CMHC Insurance
Calculates the Loan-to-Value ratio and determines insurance requirements.

- **LTV (Loan-to-Value):**
  - Formula: `(Mortgage Amount / Property Value) * 100`
  - Max Insurable: ≤ 95%
  
- **Insurance Logic:**
  - If LTV > 80%, insurance is required.
  - Premium Tiers:
    - 80.01% - 85.00%: 2.80%
    - 85.01% - 90.00%: 3.10%
    - 90.01% - 95.00%: 4.00%

## Usage Example

```python
from modules.decision_service.services import DecisionEngine
from decimal import Decimal

engine = DecisionEngine()

result = await engine.evaluate(
    loan_amount=Decimal("450000"),
    property_value=Decimal("500000"),
    annual_income=Decimal("120000"),
    contract_rate=Decimal("4.5"),
    monthly_property_tax=Decimal("300"),
    monthly_heating=Decimal("150"),
    monthly_debt_payments=Decimal("500")
)

if result.decision == "APPROVED":
    print(f"Loan approved with LTV: {result.ltv_ratio}%")
```

## Regulatory Compliance Notes
- **Auditability:** All ratio calculations are logged with detailed breakdowns for audit trails (FINTRAC).
- **Precision:** All financial calculations use `Decimal` to prevent floating-point errors.
- **PIPEDA:** No raw PII (SIN/DOB) is processed by this engine; only financial identifiers are used.
```

### 3. Configuration Notes
**File:** `.env.example` (Update)

```bash
# Decision Service Configuration
# Note: Regulatory limits (GDS 39%, TDS 44%, Stress Test Floor 5.25%) 
# are enforced via code constants per OSFI B-20. 
# No specific module configuration is required for these values.

# Optional: Enable detailed calculation logging for audit purposes
DECISION_SERVICE_VERBOSE_LOGGING=false
```

### 4. Changelog Update
**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Decision Service: New deterministic rule engine for underwriting.
- Decision Service: Implementation of OSFI B-20 Stress Test (min 5.25%).
- Decision Service: GDS/TDS ratio calculations with regulatory limits (39%/44%).
- Decision Service: CMHC Insurance premium tier logic and LTV calculation.
- Decision Service: API endpoint `POST /api/v1/decision/evaluate`.

### Changed
- Updated common exceptions to support underwriting specific error codes.

### Fixed
- N/A
```