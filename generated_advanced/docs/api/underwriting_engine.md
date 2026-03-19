Here is the documentation for the **Underwriting Engine** module.

### 1. API Documentation

**File:** `docs/api/underwriting_engine.md`

```markdown
# Underwriting Engine API

## POST /api/v1/underwriting/calculate

Performs a full underwriting evaluation based on OSFI B-20, CMHC, and LTV rules. This endpoint is stateless and does not save data to the database.

**Request:**
```json
{
  "annual_income": "120000.00",
  "property_value": "600000.00",
  "down_payment": "120000.00",
  "contract_rate": "4.50",
  "amortization_months": 300,
  "property_tax_annual": "3600.00",
  "heating_monthly": "150.00",
  "condo_fees_monthly": "0.00",
  "monthly_debts": "450.00"
}
```

**Response (200 OK):**
```json
{
  "decision": "APPROVED",
  "qualifying_rate": "5.25",
  "ltv_ratio": "80.00",
  "gds_ratio": "28.50",
  "tds_ratio": "32.50",
  "cmhc_required": false,
  "cmhc_premium": "0.00",
  "monthly_payment": "2683.51",
  "stress_test_monthly_payment": "2967.23",
  "warnings": []
}
```

**Errors:**
- **400 Bad Request:** Invalid input data (e.g., negative values, down payment > property value).
- **422 Unprocessable Entity:** Validation error (e.g., missing required fields).
- **401 Unauthorized:** Not authenticated.

---
```

### 2. Module README

**File:** `docs/modules/underwriting_engine.md`

```markdown
# Underwriting Engine Module

## Overview
The Underwriting Engine is the core decision-making component of the Canadian Mortgage Underwriting System. It evaluates borrower financial data against Canadian regulatory standards (OSFI B-20, CMHC) to determine mortgage eligibility.

## Key Functions

### Stress Test (OSFI B-20)
Calculates the minimum qualifying rate required for mortgage approval.
- **Logic:** `max(contract_rate + 2%, 5.25%)`
- **Usage:** Ensures borrowers can afford payments if interest rates rise.

### GDS Calculation (Gross Debt Service Ratio)
Measures the percentage of gross income spent on housing costs.
- **Formula:** `(PITH + 50% of Condo Fees) / Gross Monthly Income`
- **Limit:** Maximum 39%.
- **Components:**
  - **P:** Principal + Interest (calculated at qualifying rate)
  - **I:** Property Taxes (monthly)
  - **T:** Heating Costs
  - **H:** (Half of Condo Fees if applicable)

### TDS Calculation (Total Debt Service Ratio)
Measures the percentage of gross income spent on housing plus all other debts.
- **Formula:** `(PITH + All Other Debts + 50% of Condo Fees) / Gross Monthly Income`
- **Limit:** Maximum 44%.

### LTV & Down Payment Rules
Calculates the Loan-to-Value ratio and validates minimum down payment requirements.
- **LTV Formula:** `Loan Amount / Property Value`
- **Down Payment Rules:**
  - 5% for first $500,000
  - 10% for portion between $500,000 and $1,000,000
  - 20% for portion over $1,000,000

### CMHC Insurance Logic
Determines if default insurance is required and calculates the premium.
- **Trigger:** LTV > 80%
- **Premium Tiers (applied to Loan Amount):**
  - 80.01% - 85.00%: 2.80%
  - 85.01% - 90.00%: 3.10%
  - 90.01% - 95.00%: 4.00%
- **Note:** Premium is typically added to the mortgage principal.

## Usage Example

```python
from modules.underwriting_engine.services import UnderwritingService

service = UnderwritingService()

# Input data usually comes from the Pydantic schema
data = {
    "annual_income": Decimal("120000.00"),
    "property_value": Decimal("600000.00"),
    "down_payment": Decimal("30000.00"), # Triggers CMHC
    "contract_rate": Decimal("4.0"),
    # ... other fields
}

result = await service.evaluate_application(data)

if result.decision == "APPROVED":
    print(f"Approved! GDS: {result.gds_ratio}%")
else:
    print(f"Declined: {result.rejection_reason}")
```

## Regulatory Compliance Notes
- **Logging:** All ratio calculations are logged with a breakdown for audit purposes.
- **Precision:** All financial calculations utilize `Decimal` to prevent floating-point errors.
- **PIPEDA:** No PII (SIN/DOB) is required for the calculation engine itself; it relies on financial aggregates.
```

### 3. Configuration Notes

**File:** `.env.example` (Update/Additions)

```bash
# ... existing config ...

# Underwriting Engine Configuration
# The minimum floor rate for the OSFI B-20 stress test (currently 5.25%)
# Change this if OSFI regulations change without redeploying code.
UNDERWRITING_MIN_QUALIFYING_RATE=5.25

# CMHC Premium Tiers (expressed as decimals for calculation)
# Tier 1: 80.01% - 85.00%
CMHC_TIER_1_RATE=0.028
# Tier 2: 85.01% - 90.00%
CMHC_TIER_2_RATE=0.031
# Tier 3: 90.01% - 95.00%
CMHC_TIER_3_RATE=0.04
```