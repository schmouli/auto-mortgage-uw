Here is the documentation for the Underwriting Engine module.

### 1. API Documentation

**File:** `docs/api/underwriting_engine.md`

```markdown
# Underwriting Engine API

## POST /api/v1/underwriting/calculate

Performs a stateless underwriting calculation to determine qualification status based on OSFI B-20 and CMHC guidelines. This endpoint does not persist data to the database and is intended for pre-qualification scenarios.

**Request:**
```json
{
  "purchase_price": "500000.00",
  "down_payment": "25000.00",
  "annual_income": "120000.00",
  "contract_rate": "4.50",
  "amortization_years": 25,
  "property_tax_annual": "3600.00",
  "heating_monthly": "150.00",
  "condo_fees_monthly": "0.00",
  "debts_monthly": "450.00"
}
```

**Response (200):**
```json
{
  "qualifying_rate": "5.25",
  "monthly_payment": "2462.32",
  "gds_ratio": "28.50",
  "tds_ratio": "33.50",
  "ltv_ratio": "95.00",
  "cmhc_insurance_required": true,
  "cmhc_premium_rate": "4.00",
  "cmhc_premium_amount": "19000.00",
  "is_approved": true,
  "limit_checks": {
    "gds_pass": true,
    "tds_pass": true,
    "down_payment_pass": true
  }
}
```

**Errors:**
- 400: Invalid input (e.g., negative values, down payment < minimum requirement).
- 422: Validation error (missing fields).
- 500: Internal calculation error.

---

## POST /api/v1/underwriting/applications

Creates a formal underwriting assessment record. This endpoint performs the same calculations as `/calculate` but persists the result for audit purposes (FINTRAC compliance). 

**Note:** PII such as SIN and DOB must be encrypted prior to submission or handled via the identity verification headers. This endpoint expects an applicant token.

**Request:**
```json
{
  "application_id": "uuid-string",
  "applicant_token": "hashed_token_reference",
  "scenario": {
    "purchase_price": "750000.00",
    "down_payment": "150000.00",
    "annual_income": "180000.00",
    "contract_rate": "3.90",
    "amortization_years": 30,
    "property_tax_annual": "5000.00",
    "heating_monthly": "200.00",
    "condo_fees_monthly": "500.00",
    "debts_monthly": "800.00"
  }
}
```

**Response (201):**
```json
{
  "id": "assessment-uuid",
  "application_id": "uuid-string",
  "decision": "APPROVED",
  "gds_ratio": "24.10",
  "tds_ratio": "29.50",
  "ltv_ratio": "80.00",
  "cmhc_insurance_required": false,
  "created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 400: Calculation failed regulatory constraints.
- 401: Invalid or missing applicant token.
- 422: Validation error.
```

### 2. Module README

**File:** `docs/modules/underwriting_engine.md`

```markdown
# Underwriting Engine Module

## Overview
The Underwriting Engine is responsible for evaluating mortgage applications against Canadian regulatory standards, specifically OSFI B-20 (Stress Testing), CMHC insurance requirements, and standard debt service ratios.

## Key Functions & Algorithms

### 1. OSFI B-20 Stress Test
The engine enforces the minimum qualifying rate for mortgage approvals.
- **Formula:** `qualifying_rate = max(contract_rate + 2.0%, 5.25%)`
- All payment calculations used in ratio analysis utilize this qualifying rate, not the contract rate.

### 2. Down Payment Requirements (LTV Rules)
Minimum down payment is enforced based on the property value:
- **5%** for the first $500,000.
- **10%** for the portion between $500,000 and $1,000,000.
- **20%** for portions above $1,000,000 (Note: Logic adjusted to reflect standard $1.5M+ or $1M+ cutoffs as per specific business rules, defaulting to: 5% ($500k), 10% ($500k-$1.5M), 20% ($1.5M+) as per requirements).

### 3. Debt Service Ratios
Financial ratios are calculated using `Decimal` precision to ensure auditability.

**GDS (Gross Debt Service Ratio)**
- **Formula:** `(Monthly_PITI + 50% of Condo_Fees) / Gross_Monthly_Income`
- **Limit:** Must be ≤ 39%.

**TDS (Total Debt Service Ratio)**
- **Formula:** `(Monthly_PITI + All_Other_Debts + 50% of Condo_Fees) / Gross_Monthly_Income`
- **Limit:** Must be ≤ 44%.

*Note: PITH = Principal + Interest + Taxes + Heating.*

### 4. CMHC Insurance Logic
Determines if default insurance is required based on Loan-to-Value (LTV) and calculates the premium.

**LTV Calculation:**
`LTV = (Purchase_Price - Down_Payment) / Purchase_Price`

**Insurance Trigger:**
If `LTV > 80%`, insurance is required.

**Premium Tiers:**
| LTV Range | Premium Rate |
|-----------|--------------|
| 80.01% - 85.00% | 2.80% |
| 85.01% - 90.00% | 3.10% |
| 90.01% - 95.00% | 4.00% |

## Usage Examples

### Python Client Usage
```python
import httpx

async def check_qualification():
    payload = {
        "purchase_price": "600000.00",
        "down_payment": "120000.00", # 20% down
        "annual_income": "150000.00",
        "contract_rate": "4.0",
        "amortization_years": 25,
        "property_tax_annual": "4000.00",
        "heating_monthly": "120.00",
        "condo_fees_monthly": "0.00",
        "debts_monthly": "500.00"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post("http://api/v1/underwriting/calculate", json=payload)
        result = response.json()
        
        if result["is_approved"]:
            print(f"Approved! GDS: {result['gds_ratio']}%, TDS: {result['tds_ratio']}%")
        else:
            print("Declined.")
```

## Regulatory Compliance Notes
- **Auditability:** Every calculation step (inputs, rates used, intermediate values) is logged via `structlog` with a `correlation_id`.
- **Data Minimization:** The engine only requests financial data required for underwriting.
- **PIPEDA:** SIN/DOB are never processed by the calculation logic; only financial metrics are used.
```

### 3. Changelog Updates

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Underwriting Engine: New module for mortgage qualification logic.
- POST /api/v1/underwriting/calculate: Stateless endpoint for pre-qualification.
- POST /api/v1/underwriting/applications: Stateful endpoint for formal assessment creation.
- OSFI B-20 Stress Test implementation: Qualifying rate enforcement (max(contract + 2%, 5.25%)).
- CMHC Insurance Logic: Automated premium calculation based on LTV tiers.
- Ratio Validation: GDS (≤39%) and TDS (≤44%) checks with detailed logging.

### Changed
- Updated common/config.py to support financial precision settings (Decimal context).

### Fixed
- N/A
```

### 4. Environment Variables

**File:** `.env.example`

```bash
# ... existing vars ...

# Underwriting Engine Configuration
# Minimum buffer for stress test (default 2.0% per OSFI B-20)
UNDERWRITING_STRESS_TEST_BUFFER=0.02

# Floor rate for stress test (default 5.25% per OSFI B-20)
UNDERWRITING_STRESS_TEST_FLOOR_RATE=0.0525

# CMHC Premium Tiers (comma separated: upper_bound:rate)
UNDERWRITING_CMHC_TIERS="0.85:0.028,0.90:0.031,0.95:0.04"
```