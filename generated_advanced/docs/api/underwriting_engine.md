Here is the documentation for the **Underwriting Engine** module.

### 1. API Documentation

**File:** `docs/api/underwriting_engine.md`

```markdown
# Underwriting Engine API

## POST /api/v1/underwriting/calculate

Performs a stateless mortgage qualification calculation. This endpoint applies OSFI B-20 stress tests, calculates GDS/TDS ratios, determines CMHC insurance requirements, and evaluates LTV rules without saving the data to the database.

**Request:**
```json
{
  "application_amount": "450000.00",
  "down_payment": "90000.00",
  "property_value": "540000.00",
  "annual_income": "120000.00",
  "contract_rate": "4.50",
  "amortization_years": 25,
  "heating_cost": "150.00",
  "property_tax": "300.00",
  "condo_fees": "0.00",
  "monthly_debts": "450.00"
}
```

**Response (200):**
```json
{
  "is_qualified": true,
  "decision": "APPROVED",
  "qualifying_rate": "6.50",
  "calculations": {
    "gds_ratio": "28.50",
    "tds_ratio": "32.10",
    "ltv_ratio": "83.33",
    "loan_amount": "450000.00",
    "monthly_payment": "2495.00"
  },
  "regulatory": {
    "gds_limit": "39.00",
    "tds_limit": "44.00",
    "cmhc_required": true,
    "cmhc_premium_rate": "2.80",
    "cmhc_premium_amount": "12600.00",
    "min_down_payment_ok": true
  }
}
```

**Errors:**
- `400`: Invalid input data (e.g., negative values, down payment > property value).
- `422`: Validation error (e.g., missing required fields, malformed Decimal).
- `401`: Not authenticated.

---

## POST /api/v1/underwriting/submit

Submits a full underwriting application for processing. This endpoint performs the same calculations as `/calculate` but persists the result to the database for audit purposes (FINTRAC compliant).

**Request:**
```json
{
  "applicant_id": "uuid-string",
  "application_amount": "450000.00",
  "down_payment": "90000.00",
  "property_value": "540000.00",
  "annual_income": "120000.00",
  "contract_rate": "4.50",
  "amortization_years": 25,
  "heating_cost": "150.00",
  "property_tax": "300.00",
  "condo_fees": "0.00",
  "monthly_debts": "450.00"
}
```

**Response (201):**
```json
{
  "id": "uuid-string",
  "status": "PENDING_REVIEW",
  "decision": "APPROVED",
  "created_at": "2026-03-02T14:30:00Z",
  "updated_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- `400`: Invalid input data.
- `404`: Applicant not found.
- `422`: Validation error.
- `401`: Not authenticated.
```

### 2. Module README

**File:** `docs/modules/underwriting_engine.md`

```markdown
# Underwriting Engine Module

## Overview
The Underwriting Engine is the core decision-making component of the Canadian Mortgage Underwriting System. It implements the mathematical and regulatory logic required to assess mortgage risk based on Canadian guidelines (OSFI B-20, CMHC).

## Key Functions

### Stress Testing (OSFI B-20)
Calculates the minimum qualifying rate for the mortgage application.
- **Logic:** `qualifying_rate = max(contract_rate + 2%, 5.25%)`
- **Usage:** Ensures the borrower can afford payments if rates rise.

### Ratio Calculations
Determines the borrower's ability to service debt.

1.  **GDS (Gross Debt Service Ratio)**
    -   **Formula:** `(Principal + Interest + Taxes + Heating + 50% Condo Fees) / Gross Monthly Income`
    -   **Limit:** Must be ≤ 39%.

2.  **TDS (Total Debt Service Ratio)**
    -   **Formula:** `(PITH + All Other Monthly Debts + 50% Condo Fees) / Gross Monthly Income`
    -   **Limit:** Must be ≤ 44%.

### LTV & Down Payment Logic
Evaluates the loan-to-value ratio against minimum down payment rules.
- **LTV:** `Loan Amount / Property Value`
- **Rules:**
  - Property ≤ $500k: Min 5% down payment.
  - Property $500k - $1.5M: Min 5% on first $500k, 10% on remainder.
  - Property > $1.5M: Min 20% down payment.

### CMHC Insurance Premium Calculation
Determines if mortgage default insurance is required and calculates the premium.
- **Trigger:** LTV > 80%
- **Tiers:**
  - 80.01% - 85.00%: 2.80%
  - 85.01% - 90.00%: 3.10%
  - 90.01% - 95.00%: 4.00%
- **Premium Amount:** `Loan Amount * (Premium Rate / (1 - Premium Rate))` (Amortized over loan life or paid upfront depending on business logic, here calculated as total premium).

## Usage Example

To run a calculation, call the `UnderwritingService`:

```python
from decimal import Decimal
from modules.underwriting_engine.services import UnderwritingService

service = UnderwritingService()

result = await service.calculate_qualification(
    application_amount=Decimal("450000"),
    down_payment=Decimal("90000"),
    property_value=Decimal("540000"),
    annual_income=Decimal("120000"),
    contract_rate=Decimal("4.5"),
    # ... other fields
)

if result.is_qualified:
    print(f"Approved. GDS: {result.gds_ratio}%")
else:
    print(f"Declined. Reason: {result.rejection_reason}")
```

## Audit & Compliance
- **PIPEDA:** SIN and DOB are never logged or returned in API responses.
- **FINTRAC:** All submitted applications are immutable records with `created_at` timestamps.
```

### 3. Configuration & Changelog

**File:** `.env.example` (Append or update)

```bash
# Underwriting Engine Configuration
# Minimum stress test floor rate (OSFI B-20 standard is 5.25%)
UNDERWRITING_STRESS_TEST_FLOOR=5.25

# Hard limits for ratios (OSFI B-20)
UNDERWRITING_GDS_LIMIT=39
UNDERWRITING_TDS_LIMIT=44
```

**File:** `CHANGELOG.md` (Append)

```markdown
## [2026-03-02]
### Added
- Underwriting Engine: Core module for mortgage qualification logic.
- POST /api/v1/underwriting/calculate: Stateless calculation endpoint.
- POST /api/v1/underwriting/submit: Persistent application submission endpoint.
- Implemented OSFI B-20 stress test logic (contract_rate + 2% vs 5.25%).
- Implemented GDS/TDS calculation with 50% condo fee inclusion.
- Implemented CMHC insurance premium tiers (2.80%, 3.10%, 4.00%).
- Implemented LTV and minimum down payment validation rules ($500k/$1.5M thresholds).

### Changed
- N/A

### Fixed
- N/A
```