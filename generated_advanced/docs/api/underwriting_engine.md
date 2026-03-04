# Underwriting Engine API Documentation

## POST /api/v1/underwriting/calculate

Performs a full mortgage qualification analysis based on OSFI B-20 and CMHC guidelines. This endpoint is stateless and does not save data to the database.

**Request Headers:**
- `Content-Type: application/json`
- `Authorization: Bearer <token>` (if auth is required)

**Request Body:**
```json
{
  "property_value": "750000.00",
  "down_payment": "150000.00",
  "annual_income": "120000.00",
  "property_tax_monthly": "350.00",
  "heating_monthly": "125.00",
  "condo_fees_monthly": "0.00",
  "debts_monthly": "500.00",
  "contract_rate": "4.50",
  "amortization_years": 25
}
```

**Response (200 OK):**
```json
{
  "decision": "APPROVED",
  "qualifying_rate": "5.25",
  "ltv_ratio": "80.00",
  "gds_ratio": "28.50",
  "tds_ratio": "32.10",
  "cmhc_premium_total": "0.00",
  "monthly_payment": "3392.41",
  "breakdown": {
    "stress_test_applied": true,
    "max_gds_limit": "39.00",
    "max_tds_limit": "44.00",
    "insurance_required": false
  }
}
```

**Response (200 OK - Declined):**
```json
{
  "decision": "DECLINED",
  "qualifying_rate": "6.50",
  "ltv_ratio": "95.00",
  "gds_ratio": "42.00",
  "tds_ratio": "45.00",
  "cmhc_premium_total": "19000.00",
  "monthly_payment": "4500.00",
  "breakdown": {
    "stress_test_applied": true,
    "max_gds_limit": "39.00",
    "max_tds_limit": "44.00",
    "insurance_required": true
  },
  "rejection_reasons": [
    "GDS ratio 42.00% exceeds maximum 39.00%",
    "TDS ratio 45.00% exceeds maximum 44.00%"
  ]
}
```

**Error Responses:**
- `400 Bad Request`: Invalid input data (e.g., negative numbers).
  ```json
  {
    "detail": "Down payment cannot be negative.",
    "error_code": "INVALID_INPUT"
  }
  ```
- `422 Unprocessable Entity`: Pydantic validation error.
  ```json
  {
    "detail": [
      {
        "loc": ["body", "annual_income"],
        "msg": "ensure this value is greater than 0",
        "type": "greater_than"
      }
    ]
  }
  ```

---

# Underwriting Engine Module

## Overview
The Underwriting Engine is the core decision-making module for the Canadian Mortgage Underwriting System. It implements regulatory algorithms to determine borrower eligibility based on financial data and property specifics. It operates as a stateless service performing calculations on demand without persisting financial data (to ensure PII protection and speed).

## Key Functions

### 1. Stress Test Calculation (OSFI B-20)
Determines the minimum qualifying rate for the mortgage.
- **Logic:** `qualifying_rate = max(contract_rate + 2%, 5.25%)`
- **Usage:** Used as the discount rate for mortgage payment calculations to ensure borrower can handle rate increases.

### 2. GDS (Gross Debt Service) Ratio
Calculates the percentage of gross income used for housing costs.
- **Formula:** `(PITH + 50% of Condo Fees) / Gross Monthly Income`
- **Components:**
  - **P**rincipal + **I**nterest (calculated at qualifying rate)
  - **P**roperty Taxes
  - **H**eating (estimated at $125/mo or actual)
- **Limit:** Max 39%.

### 3. TDS (Total Debt Service) Ratio
Calculates the percentage of gross income used for housing costs plus other debts.
- **Formula:** `(PITH + 50% of Condo Fees + All Other Debts) / Gross Monthly Income`
- **Limit:** Max 44%.

### 4. LTV (Loan-to-Value) & Down Payment
Validates minimum equity requirements.
- **< $500k:** 5% minimum down payment.
- **$500k - $1.5M:** 5% on first $500k, 10% on remainder.
- **> $1.5M:** 20% minimum down payment.
- **Formula:** `LTV = (Property Value - Down Payment) / Property Value`

### 5. CMHC Insurance Premium
Calculates insurance premium based on LTV if applicable.
- **80.01% - 85.00%:** 2.80% of loan amount.
- **85.01% - 90.00%:** 3.10% of loan amount.
- **90.01% - 95.00%:** 4.00% of loan amount.
- **> 95%:** Declined (Standard cap).

## Usage Example

```python
from modules.underwriting_engine.services import UnderwritingService

service = UnderwritingService()

# Input data typically comes from the Pydantic schema
result = await service.calculate_qualification(
    property_value=Decimal("500000.00"),
    down_payment=Decimal("25000.00"),
    annual_income=Decimal("85000.00"),
    property_tax_monthly=Decimal("300.00"),
    heating_monthly=Decimal("100.00"),
    condo_fees_monthly=Decimal("0.00"),
    debts_monthly=Decimal("400.00"),
    contract_rate=Decimal("4.9"),
    amortization_years=25
)

if result.decision == "APPROVED":
    print(f"Qualified! Monthly payment: {result.monthly_payment}")
else:
    print(f"Declined: {result.rejection_reasons}")
```

## Compliance Notes
- **PIPEDA:** No Personally Identifiable Information (PII) such as SIN or DOB is required for calculation. If passed, it is ignored.
- **OSFI B-20:** All ratio calculations utilize the qualifying rate, not the contract rate.
- **Logging:** Calculation breakdowns are logged for audit purposes but do not include specific income values or asset amounts (only ratios are logged).

---

# Configuration Updates (.env.example)

Add the following variables to your `.env.example` file to configure the Underwriting Engine module:

```bash
# Underwriting Engine Configuration
# Minimum floor for stress test rate (OSFI B-20 guideline)
UNDERWRITING_QUALIFYING_RATE_FLOOR=5.25

# Default heating cost estimate if not provided (CAD/month)
UNDERWRITING_DEFAULT_HEATING_COST=125.00

# Maximum amortization period allowed (years)
UNDERWRITING_MAX_AMORTIZATION_YEARS=25
```