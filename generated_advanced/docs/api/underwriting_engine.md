# Underwriting Engine Documentation

## 1. API Documentation

**File:** `docs/api/Underwriting Engine.md`

```markdown
# Underwriting Engine API

This module handles the core decision-making logic for mortgage qualification, including OSFI B-20 stress testing, GDS/TDS ratio calculations, and CMHC insurance premium determination.

## POST /api/v1/underwriting/calculate

Performs a full underwriting calculation based on provided financial data. This endpoint does not save data to the database; it is a stateless calculation engine.

**Request:**

```json
{
  "loan_amount": "450000.00",
  "property_value": "500000.00",
  "down_payment": "50000.00",
  "contract_rate": "4.50",
  "amortization_years": 25,
  "annual_income": "120000.00",
  "property_tax_annual": "3600.00",
  "heating_cost_monthly": "150.00",
  "condo_fees_monthly": "0.00",
  "monthly_debt_payments": "450.00"
}
```

**Response (200 OK):**

```json
{
  "decision": "APPROVED",
  "qualifying_rate": "6.50",
  "monthly_payment": "2495.32",
  "gds_ratio": "27.95",
  "tds_ratio": "31.71",
  "ltv_ratio": "90.00",
  "cmhc_insurance_required": true,
  "cmhc_premium_amount": "12600.00",
  "cmhc_premium_rate": "2.80",
  "total_loan_amount": "462600.00",
  "stress_test_monthly_payment": "2915.61",
  "messages": []
}
```

**Response (200 OK - Rejection Example):**

```json
{
  "decision": "DECLINED",
  "qualifying_rate": "5.25",
  "monthly_payment": "2800.00",
  "gds_ratio": "42.00",
  "tds_ratio": "45.00",
  "ltv_ratio": "95.00",
  "cmhc_insurance_required": true,
  "cmhc_premium_amount": "0.00",
  "cmhc_premium_rate": "0.00",
  "total_loan_amount": "0.00",
  "stress_test_monthly_payment": "0.00",
  "messages": [
    "GDS ratio 42.00% exceeds maximum limit of 39.00%.",
    "Down payment insufficient for property value over $500,000.00."
  ]
}
```

**Errors:**
- `400 Bad Request`: Invalid input data (e.g., negative values, amortization > 30 years).
- `422 Unprocessable Entity`: Pydantic validation error (malformed JSON or incorrect types).
- `500 Internal Server Error`: Unexpected calculation failure.

**Notes:**
- All financial values must be strings representing Decimals to ensure precision.
- The `qualifying_rate` is calculated as `max(contract_rate + 2%, 5.25%)` per OSFI B-20.
- GDS includes 50% of condo fees. TDS includes 100% of other debts.
```

---

## 2. Module README

**File:** `docs/modules/Underwriting Engine.md`

```markdown
# Underwriting Engine Module

## Overview
The Underwriting Engine is the core logic component of the Canadian Mortgage Underwriting System. It applies regulatory rules (OSFI B-20, CMHC) to determine mortgage eligibility. It is designed to be stateless regarding data persistence, focusing purely on financial algorithms.

## Key Functions & Algorithms

### 1. Stress Testing (OSFI B-20)
Calculates the minimum qualifying rate a borrower must afford.
- **Formula:** `max(contract_rate + 2.0%, 5.25%)`
- **Usage:** Used to calculate the `stress_test_monthly_payment` to ensure the borrower can handle rate increases.

### 2. GDS Calculation (Gross Debt Service Ratio)
Measures the percentage of gross income used for housing costs.
- **Formula:** `(Monthly Principal + Interest + Taxes + Heating + (50% * Condo Fees)) / Gross Monthly Income`
- **Limit:** Must be ≤ 39%.

### 3. TDS Calculation (Total Debt Service Ratio)
Measures the percentage of gross income used for housing plus all other debts.
- **Formula:** `(PITH + (50% * Condo Fees) + Monthly Debts) / Gross Monthly Income`
- **Limit:** Must be ≤ 44%.

### 4. LTV & Down Payment Rules
Determines if the down payment meets Canadian regulations.
- **Property Value ≤ $500,000:** Min 5% down payment.
- **Property Value $500,000 - $1,000,000:** 5% on first $500k, 10% on remainder.
- **Property Value > $1,000,000:** Min 20% down payment (CMHC insurance unavailable).

### 5. CMHC Insurance Logic
Calculates default insurance premiums if LTV > 80%.
- **80.01% - 85.00% LTV:** 2.80% premium
- **85.01% - 90.00% LTV:** 3.10% premium
- **90.01% - 95.00% LTV:** 4.00% premium
- **> 95% LTV:** Declined (Standard insurance cap)

## Usage Example

```python
from modules.underwriting_engine.services import UnderwritingService
from decimal import Decimal

service = UnderwritingService()

result = await service.calculate_underwriting(
    loan_amount=Decimal("450000"),
    property_value=Decimal("500000"),
    down_payment=Decimal("50000"),
    contract_rate=Decimal("4.5"),
    amortization_years=25,
    annual_income=Decimal("120000"),
    property_tax_annual=Decimal("3600"),
    heating_cost_monthly=Decimal("150"),
    condo_fees_monthly=Decimal("0"),
    monthly_debt_payments=Decimal("450")
)

if result.decision == "APPROVED":
    print(f"Qualified! GDS: {result.gds_ratio}%")
else:
    print(f"Declined: {result.messages}")
```

## Dependencies
- `decimal`: For all financial math (严禁 float).
- `pydantic`: For input validation.
```

---

## 3. Configuration Notes

**File:** `.env.example` (Append these entries)

```bash
# Underwriting Engine Configuration
# Minimum floor for OSFI stress test (per B-20 guidelines)
UNDERWRITING_STRESS_TEST_MIN_RATE=5.25

# Minimum allowed credit score (if implemented in future logic)
UNDERWRITING_MIN_CREDIT_SCORE=600

# Switch to enable/disable strict CMHC insurance validation
UNDERWRITING_CMHC_STRICT_MODE=true
```