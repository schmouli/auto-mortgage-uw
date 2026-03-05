# Underwriting Engine API

## Overview
The Underwriting Engine module provides endpoints to evaluate mortgage applications against Canadian regulatory standards (OSFI B-20, CMHC). It performs real-time calculations for Debt Service ratios (GDS/TDS), Loan-to-Value (LTV), and CMHC insurance requirements without persisting data, or allows submitting a full application for storage.

## POST /api/v1/underwriting/calculate

Performs a qualification check based on provided financial data. This endpoint executes the underwriting algorithms but does not save the application to the database.

**Request:**
```json
{
  "application_date": "2026-03-02",
  "loan_amount": "450000.00",
  "property_value": "500000.00",
  "down_payment": "50000.00",
  "annual_income": "120000.00",
  "contract_rate": "4.50",
  "amortization_years": 25,
  "property_tax_annual": "3000.00",
  "heating_cost_monthly": "150.00",
  "condo_fees_monthly": "0.00",
  "monthly_debts": "500.00"
}
```

**Response (200):**
```json
{
  "is_qualified": true,
  "qualifying_rate": "6.50",
  "gds_ratio": "28.50",
  "tds_ratio": "32.00",
  "ltv_ratio": "90.00",
  "cmhc": {
    "insurance_required": true,
    "premium_percentage": "3.10",
    "premium_amount": "13950.00",
    "total_loan_amount": "463950.00"
  },
  "stress_test": {
    "passed": true,
    "monthly_payment_at_qualifying_rate": "3145.12"
  },
  "rejection_reasons": []
}
```

**Errors:**
- 400: Invalid financial input (e.g., negative values, down payment < minimum requirement).
- 422: Validation error (missing required fields).
- 401: Not authenticated.

---

## POST /api/v1/underwriting/submit

Creates a new mortgage application record by running the underwriting engine and persisting the result. This action creates an immutable audit trail per FINTRAC requirements.

**Request:**
```json
{
  "applicant_id": "uuid-of-applicant",
  "loan_amount": "800000.00",
  "property_value": "1000000.00",
  "down_payment": "200000.00",
  "annual_income": "200000.00",
  "contract_rate": "5.00",
  "amortization_years": 30,
  "property_tax_annual": "6000.00",
  "heating_cost_monthly": "200.00",
  "condo_fees_monthly": "500.00",
  "monthly_debts": "1000.00"
}
```

**Response (201):**
```json
{
  "id": "uuid-of-application",
  "status": "Approved",
  "created_at": "2026-03-02T14:30:00Z",
  "decision_details": {
    "gds_ratio": "25.40",
    "tds_ratio": "30.10",
    "ltv_ratio": "80.00",
    "insurance_required": false
  }
}
```

**Errors:**
- 400: Regulatory limit exceeded (e.g., TDS > 44%).
- 409: Duplicate application submission.
- 422: Validation error.

---

# Underwriting Engine Module Documentation

## Overview
The Underwriting Engine is the core decision-making component of the Canadian Mortgage Underwriting System. It encapsulates business logic required to validate borrower creditworthiness against OSFI B-20 guidelines and CMHC insurance default rules.

### Key Functions

1.  **Stress Test Calculation (OSFI B-20)**
    *   Determines the minimum qualifying rate a borrower must afford.
    *   **Formula:** `max(contract_rate + 2.00%, 5.25%)`
    *   The resulting monthly payment is used for GDS/TDS calculations.

2.  **GDS (Gross Debt Service)**
    *   Measures the percentage of gross income going toward housing costs.
    *   **Formula:** `(Principal + Interest + Taxes + Heat + 50% Condo Fees) / Gross Monthly Income`
    *   **Limit:** Must not exceed 39%.

3.  **TDS (Total Debt Service)**
    *   Measures the percentage of gross income going toward housing costs plus all other debts.
    *   **Formula:** `(PITH + All Other Debts + 50% Condo Fees) / Gross Monthly Income`
    *   **Limit:** Must not exceed 44%.

4.  **LTV (Loan-to-Value) & Down Payment**
    *   Validates minimum down payment requirements:
        *   5% on first $500,000
        *   10% on portion between $500,000 and $1,000,000
        *   20% on amounts over $1,000,000
    *   **Formula:** `Loan Amount / Property Value`

5.  **CMHC Insurance Logic**
    *   Calculates insurance premiums based on LTV tiers.
    *   **Tiers:**
        *   80.01% - 85.00%: 2.80%
        *   85.01% - 90.00%: 3.10%
        *   90.01% - 95.00%: 4.00%
    *   If LTV > 80%, insurance is mandatory.

### Usage Examples

#### Using the Service Layer Directly
```python
from decimal import Decimal
from modules.underwriting_engine.services import UnderwritingService

service = UnderwritingService()

result = await service.evaluate(
    loan_amount=Decimal("450000"),
    annual_income=Decimal("120000"),
    contract_rate=Decimal("4.5"),
    # ... other params
)

if result.is_qualified:
    print(f"Approved! GDS: {result.gds_ratio}%")
else:
    print(f"Denied: {result.rejection_reasons}")
```

### Compliance Notes
*   **Logging:** All calculations (GDS, TDS, LTV) are logged with a `correlation_id` for auditability. Specific financial values (income, exact debt amounts) are masked in logs to comply with PIPEDA.
*   **Precision:** All monetary values use `Decimal` to prevent floating-point rounding errors.

---

# Configuration Notes

## Environment Variables

Update `.env.example` with the following variables for the Underwriting Engine module.

```bash
# Underwriting Engine Configuration
# Minimum floor rate for OSFI B-20 stress test (default 5.25%)
UNDERWRITING_STRESS_TEST_FLOOR_RATE=5.25

# Stress test buffer percentage added to contract rate (default 2.00%)
UNDERWRITING_STRESS_TEST_BUFFER=2.00

# Maximum allowable GDS ratio (OSFI B-20 guideline)
UNDERWRITING_MAX_GDS=39

# Maximum allowable TDS ratio (OSFI B-20 guideline)
UNDERWRITING_MAX_TDS=44
```