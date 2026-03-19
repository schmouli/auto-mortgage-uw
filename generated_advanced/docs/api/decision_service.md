# Decision Service API

## POST /api/v1/decision

Evaluates a mortgage application against OSFI B-20 guidelines and internal policy rules to return an underwriting decision.

**Request:**
```json
{
  "applicant_id": "uuid-string",
  "loan_amount": "450000.00",
  "property_value": "500000.00",
  "gross_annual_income": "120000.00",
  "contract_rate": "0.049",
  "property_tax_monthly": "350.00",
  "heating_monthly": "120.00",
  "other_debts_monthly": "500.00",
  "mortgage_payment_monthly": "2500.00"
}
```

**Response (200):**
```json
{
  "decision": "APPROVED",
  "qualifying_rate": "0.0525",
  "gds_ratio": "29.70",
  "tds_ratio": "34.20",
  "ltv_ratio": "90.00",
  "insurance_required": true,
  "reasons": []
}
```

**Response (200 - Declined):**
```json
{
  "decision": "DECLINED",
  "qualifying_rate": "0.0525",
  "gds_ratio": "42.00",
  "tds_ratio": "46.50",
  "ltv_ratio": "90.00",
  "insurance_required": true,
  "reasons": [
    "GDS ratio 42.00% exceeds maximum limit of 39.00% (OSFI B-20)",
    "TDS ratio 46.50% exceeds maximum limit of 44.00% (OSFI B-20)"
  ]
}
```

**Errors:**
- `400`: Invalid input data (e.g., negative values).
- `422`: Validation error (missing required fields).
- `500`: Internal calculation error.

---

# Decision Service Module

## Overview
The Decision Service acts as the deterministic rule engine for the mortgage underwriting system. It consumes borrower and property financial data to apply regulatory (OSFI B-20, CMHC) and business logic rules. The service does not persist data itself but produces a decision result that is recorded by other services.

## Key Functions

### `calculate_stress_test(contract_rate: Decimal) -> Decimal`
Determines the qualifying interest rate used for debt service calculations.
- **Logic:** `max(contract_rate + 2%, 5.25%)`
- **Compliance:** OSFI B-20 Benchmark.

### `calculate_gds(pith: Decimal, gross_income: Decimal) -> Decimal`
Calculates the Gross Debt Service ratio.
- **Logic:** `(PITH / Gross Monthly Income) * 100`
- **Limit:** Must be ≤ 39%.
- **Compliance:** OSFI B-20.

### `calculate_tds(pith: Decimal, debts: Decimal, gross_income: Decimal) -> Decimal`
Calculates the Total Debt Service ratio.
- **Logic:** `((PITH + Other Debts) / Gross Monthly Income) * 100`
- **Limit:** Must be ≤ 44%.
- **Compliance:** OSFI B-20.

### `calculate_ltv(loan_amount: Decimal, property_value: Decimal) -> Decimal`
Calculates the Loan-to-Value ratio.
- **Logic:** `(Loan Amount / Property Value) * 100`
- **Compliance:** CMHC (Determines insurance requirement if > 80%).

### `evaluate_application(data: DecisionInput) -> DecisionOutput`
Orchestrates the calculation of all ratios and applies rule logic to return a final `APPROVED`, `REFER`, or `DECLINED` status.

## Regulatory Compliance Notes
- **OSFI B-20:** All ratio calculations strictly enforce the 39% GDS and 44% TDS limits based on the qualifying stress test rate.
- **CMHC:** LTV > 80% automatically triggers the `insurance_required` flag. LTV > 95% results in an automatic decline.
- **PIPEDA:** No Personally Identifiable Information (PII) such as SIN or DOB is required for the calculation logic, ensuring data minimization.

---

# CHANGELOG.md Update

```markdown
## [2026-03-02]
### Added
- Decision Service: New endpoints for underwriting evaluation
- Core calculations for OSFI B-20 Stress Test, GDS, TDS, and LTV
- Deterministic rule engine for mortgage approval logic
```

# .env.example Update

```bash
# Decision Service Configuration
# No specific module variables required. 
# Relies on common application settings (logging, database).
```