# Decision Service API

## POST /api/v1/decision/evaluate

Evaluate borrower data against underwriting rules to produce a final decision (Approve/Reject/Refer). This endpoint performs deterministic calculations based on OSFI B-20 guidelines and CMHC requirements.

**Request:**
```json
{
  "application_id": "str",
  "borrower_id": "str",
  "mortgage_amount": "450000.00",
  "property_value": "500000.00",
  "contract_rate": "4.50",
  "annual_income": "120000.00",
  "property_tax_annual": "3000.00",
  "heating_cost_monthly": "150.00",
  "other_debts_monthly": "500.00"
}
```

**Response (200):**
```json
{
  "application_id": "str",
  "decision": "APPROVED",
  "qualifying_rate": "6.50",
  "ratios": {
    "gds": "28.50",
    "tds": "33.10",
    "ltv": "90.00"
  },
  "insurance_required": true,
  "premium_percentage": "3.10",
  "details": "All ratios within OSFI B-20 limits."
}
```

**Errors:**
- 400: Invalid financial input (negative values, malformed decimals).
- 422: Validation error (missing required fields).
- 500: Internal calculation error.

---

## Module README

### Overview
The Decision Service acts as a pure deterministic rule engine within the Canadian Mortgage Underwriting System. It does not store data but processes extracted borrower and property metrics to determine underwriting eligibility.

### Key Functions
The core logic relies on strict adherence to OSFI B-20 and CMHC regulatory standards:

1.  **Stress Test Calculation**:
    Determines the qualifying rate used for debt service calculations.
    *   Logic: `max(contract_rate + 2.0%, 5.25%)`

2.  **GDS (Gross Debt Service)**:
    Calculates the percentage of gross income used for housing costs.
    *   Formula: `(Principal + Interest + Taxes + Heat) / Gross Monthly Income`
    *   Limit: ≤ 39%

3.  **TDS (Total Debt Service)**:
    Calculates the percentage of gross income used for housing plus all other debts.
    *   Formula: `(PITH + Other Debts) / Gross Monthly Income`
    *   Limit: ≤ 44%

4.  **LTV (Loan-to-Value)**:
    Assesses the risk of the loan amount relative to the property value.
    *   Formula: `Mortgage Amount / Property Value`
    *   CMHC Insurance: Required if LTV > 80%.

### Usage Example
The service is consumed via the `/api/v1/decision/evaluate` endpoint. It expects precise financial figures (as Decimals) and returns a structured decision object indicating approval status and the specific metrics used to reach that conclusion.

---

## Configuration Notes

The Decision Service relies on environment variables to define regulatory floors and operational settings.

### Environment Variables

```bash
# Decision Service Configuration
# Minimum qualifying rate floor (OSFI B-20 standard)
QUALIFYING_RATE_MIN=5.25

# Stress Test Margin (Contract rate + X%)
STRESS_TEST_MARGIN=2.0

# OSFI B-20 Hard Limits
GDS_LIMIT=39
TDS_LIMIT=44

# CMHC Insurance Thresholds
LTV_INSURANCE_THRESHOLD=80.0
MAX_LTV_INSURED=95.0
```

---

## Changelog Updates

```markdown
## [2026-03-02]
### Added
- Decision Service: New endpoints for underwriting evaluation
- Deterministic rule engine for OSFI B-20 compliance (GDS/TDS/Stress Test)
- CMHC insurance requirement logic based on LTV calculations

### Changed
- N/A

### Fixed
- N/A
```