# Lender Comparison & Submission API

## POST /api/v1/lenders

Register a new lending institution.

**Request:**
```json
{
  "name": "First National Bank",
  "type": "bank",
  "is_active": true,
  "logo_url": "https://example.com/logos/fnb.png",
  "submission_email": "underwriting@fnb.com",
  "notes": "Preferred lender for conventional mortgages"
}
```

**Response (201):**
```json
{
  "id": 1,
  "name": "First National Bank",
  "type": "bank",
  "is_active": true,
  "logo_url": "https://example.com/logos/fnb.png",
  "submission_email": "underwriting@fnb.com",
  "notes": "Preferred lender for conventional mortgages",
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Invalid lender type
- 422: Validation error

---

## GET /api/v1/lenders

Retrieve a list of all active lenders.

**Response (200):**
```json
[
  {
    "id": 1,
    "name": "First National Bank",
    "type": "bank",
    "is_active": true,
    "logo_url": "https://example.com/logos/fnb.png",
    "submission_email": "underwriting@fnb.com",
    "created_at": "2026-03-02T10:00:00Z"
  }
]
```

---

## POST /api/v1/lender-products

Define a new mortgage product offered by a lender.

**Request:**
```json
{
  "lender_id": 1,
  "product_name": "5-Year Fixed High-Ratio",
  "mortgage_type": "fixed",
  "term_years": 5,
  "rate": "5.29",
  "rate_type": "discounted",
  "max_ltv_insured": "95.00",
  "max_ltv_conventional": "80.00",
  "max_amortization_insured": 25,
  "max_amortization_conventional": 30,
  "min_credit_score": 680,
  "max_gds": "39.00",
  "max_tds": "44.00",
  "allows_self_employed": true,
  "allows_rental_income": true,
  "allows_gifted_down_payment": true
}
```

**Response (201):**
```json
{
  "id": 101,
  "lender_id": 1,
  "product_name": "5-Year Fixed High-Ratio",
  "mortgage_type": "fixed",
  "rate": "5.29",
  "min_credit_score": 680,
  "max_gds": "39.00",
  "max_tds": "44.00",
  "created_at": "2026-03-02T10:05:00Z"
}
```

**Errors:**
- 404: Lender not found
- 422: Invalid financial value (must be Decimal)

---

## POST /api/v1/lender-products/compare

Compare a borrower's profile against available products to find matches.
**Note:** Enforces OSFI B-20 compliance by filtering out products where borrower GDS/TDS exceed product limits.

**Request:**
```json
{
  "loan_amount": "450000.00",
  "property_value": "500000.00",
  "mortgage_type": "fixed",
  "term_years": 5,
  "credit_score": 700,
  "annual_income": "120000.00",
  "property_tax": "300.00",
  "heating": "150.00",
  "other_debt": "500.00",
  "is_self_employed": false,
  "down_payment_source": "savings"
}
```

**Response (200):**
```json
{
  "matches": [
    {
      "lender_id": 1,
      "lender_name": "First National Bank",
      "product_id": 101,
      "product_name": "5-Year Fixed High-Ratio",
      "rate": "5.29",
      "monthly_payment": "2623.54",
      "ltv": "90.00",
      "gds": "28.50",
      "tds": "33.50",
      "qualification_status": "qualified"
    }
  ],
  "disqualified_reasons": []
}
```

**Errors:**
- 422: Invalid input parameters

---

## POST /api/v1/lender-products/submit

Submit a qualified application to a specific lender product.
**Note:** Creates an immutable audit trail (FINTRAC compliant).

**Request:**
```json
{
  "application_id": 550,
  "lender_product_id": 101,
  "submission_data": {
    "applicant_name_hash": "sha256_hash...",
    "income_verified": true,
    "documents_link": "https://secure-storage.app/docs/550"
  }
}
```

**Response (201):**
```json
{
  "submission_id": "sub_123456",
  "application_id": 550,
  "lender_product_id": 101,
  "status": "submitted",
  "submitted_at": "2026-03-02T10:10:00Z",
  "confirmation_reference": "FNB-550-XYZ"
}
```

**Errors:**
- 404: Product or Application not found
- 400: Application does not meet product criteria

---

# Lender Comparison & Submission Module

## Overview
The Lender Comparison & Submission module manages the database of lending institutions and their specific mortgage products. It provides logic to automatically compare a borrower's financial profile against underwriting criteria (LTV, GDS, TDS, Credit Score) to identify eligible products and facilitates the submission process.

## Key Features
- **Lender Management:** CRUD operations for Banks, Credit Unions, Monolines, etc.
- **Product Catalog:** Detailed criteria for mortgage products (rates, terms, limits).
- **Automated Comparison:** Filters products based on OSFI B-20 compliant ratios (GDS/TDS) and LTV calculations.
- **Secure Submission:** Handles the transmission of application data to lenders, ensuring PII is handled per PIPEDA standards.

## Usage Example

### 1. Finding the Best Rate
To find the best rate for a borrower, use the `/compare` endpoint. The service calculates the GDS and TDS on the fly using the provided income and housing costs, then filters the `lender_products` table.

```python
# Conceptual Service Call
matches = await lender_service.compare_products(
    loan_amount=Decimal("450000"),
    property_value=Decimal("500000"),
    credit_score=720,
    annual_income=Decimal("95000"),
    # ... other details
)

# Returns list of products sorted by rate (lowest first)
```

### 2. Submitting an Application
Once a product is selected, the submission endpoint logs the action.

```python
# Conceptual Service Call
submission = await lender_service.submit_application(
    application_id=123,
    lender_product_id=101,
    submitted_by_user_id=5
)
```

## Regulatory Notes
- **OSFI B-20:** The `compare` endpoint strictly enforces `max_gds` (39%) and `max_tds` (44%) limits defined in the product table.
- **PIPEDA:** Submission requests must use hashed identifiers for PII; raw SIN/DOB must never be transmitted in the `submission_data` payload.

## Dependencies
- `common.database`: For SQLAlchemy sessions.
- `common.security`: For hashing applicant data before submission logs.

---

# Configuration Updates

Append the following to `.env.example`:

```ini
# Lender Comparison & Submission Configuration
# Default sender email for application submissions (if using email integration)
SUBMISSION_FROM_EMAIL=noreply@mortgage-system.com
# External API base URL for lender portals (if applicable)
LENDER_PORTAL_API_BASE_URL=https://api.lender-portal.com/v1
```

---

# CHANGELOG

## [2026-03-02]
### Added
- Lender Comparison & Submission: New endpoints for managing lenders and products.
- Lender Comparison & Submission: `POST /api/v1/lender-products/compare` for automated eligibility matching.
- Lender Comparison & Submission: `POST /api/v1/lender-products/submit` for application routing.
- Database models: `lenders` and `lender_products` with full criteria support (LTV, GDS, TDS, credit score).

### Changed
- Updated common config to include submission settings.

### Fixed
- N/A