# Lender Comparison & Submission API

## Module Overview

The **Lender Comparison & Submission** module manages the database of lending institutions and their specific mortgage products. It provides the core logic for matching borrower applications against lender criteria (LTV, GDS/TDS, credit score) and handling the submission of applications to selected lenders.

### Key Features
- **Lender Management:** CRUD operations for lenders (Banks, Credit Unions, Monolines, etc.).
- **Product Catalog:** Detailed criteria for mortgage products including rates, terms, and underwriting limits.
- **Comparison Engine:** Filters products based on borrower financials and regulatory constraints (OSFI B-20).
- **Submission Handling:** Manages the transmission of application data to lenders.

---

## API Endpoints

### 1. Create Lender

Registers a new lending institution in the system.

**POST** `/api/v1/lenders`

**Request:**
```json
{
  "name": "First National Bank",
  "type": "bank",
  "is_active": true,
  "logo_url": "https://example.com/logos/fnb.png",
  "submission_email": "submissions@fnb.com",
  "notes": "Preferred lender for high-net-worth clients"
}
```

**Response (201):**
```json
{
  "id": "uuid-v4",
  "name": "First National Bank",
  "type": "bank",
  "is_active": true,
  "logo_url": "https://example.com/logos/fnb.png",
  "submission_email": "submissions@fnb.com",
  "notes": "Preferred lender for high-net-worth clients",
  "created_at": "2026-03-02T10:00:00Z",
  "updated_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `400`: Invalid lender type provided.
- `422`: Validation error (e.g., invalid email format).

---

### 2. List Lenders

Retrieves a list of all active lenders.

**GET** `/api/v1/lenders`

**Query Parameters:**
- `is_active` (boolean, optional): Filter by active status. Default: `true`.
- `type` (string, optional): Filter by lender type (bank/credit_union/monoline/private/mfc).

**Response (200):**
```json
{
  "count": 2,
  "items": [
    {
      "id": "uuid-v4",
      "name": "First National Bank",
      "type": "bank",
      "is_active": true
    },
    {
      "id": "uuid-v4",
      "name": "Ontario Credit Union",
      "type": "credit_union",
      "is_active": true
    }
  ]
}
```

---

### 3. Create Lender Product

Defines a new mortgage product offered by a specific lender.

**POST** `/api/v1/lenders/{lender_id}/products`

**Request:**
```json
{
  "product_name": "5-Year Fixed Special",
  "mortgage_type": "fixed",
  "term_years": 5,
  "rate": "5.19",
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
  "allows_gifted_down_payment": true,
  "prepayment_options": "20/20"
}
```

**Response (201):**
```json
{
  "id": "uuid-v4",
  "lender_id": "uuid-v4",
  "product_name": "5-Year Fixed Special",
  "mortgage_type": "fixed",
  "rate": "5.19",
  "created_at": "2026-03-02T10:05:00Z"
}
```

**Errors:**
- `404`: Lender not found.
- `422`: Decimal precision error or invalid enum value.

---

### 4. Compare Products

Compares a borrower's application profile against all active products to find matches. This endpoint applies OSFI B-20 stress test logic and CMHC insurance rules during filtering.

**POST** `/api/v1/lenders/compare`

**Request:**
```json
{
  "loan_amount": "450000.00",
  "property_value": "500000.00",
  "down_payment": "50000.00",
  "is_insured": true,
  "mortgage_type": "fixed",
  "term_years": 5,
  "province": "ON",
  "credit_score": 720,
  "annual_income": "120000.00",
  "monthly_housing_costs": "2800.00",
  "monthly_debts": "500.00",
  "is_self_employed": false,
  "income_type": "salaried",
  "down_payment_source": "savings"
}
```

**Response (200):**
```json
{
  "application_summary": {
    "ltv": "90.00",
    "gds": "28.00",
    "tds": "33.00",
    "stress_test_rate": "7.19"
  },
  "matches": [
    {
      "lender_id": "uuid-v4",
      "lender_name": "First National Bank",
      "product_id": "uuid-v4",
      "product_name": "5-Year Fixed Special",
      "rate": "5.19",
      "monthly_payment": "2612.34",
      "eligibility": "eligible"
    }
  ],
  "ineligible_reasons": []
}
```

**Logic Notes:**
- **GDS/TDS:** Calculated based on inputs. If `is_insured` is true, limits are hardcoded to OSFI B-20 (GDS 39%, TDS 44%). If conventional, lender-specific limits apply.
- **Stress Test:** Qualifying rate is `max(contract_rate + 2%, 5.25%)`.

---

### 5. Submit Application

Submits a qualified application to a specific lender via their defined integration method (Email/API).

**POST** `/api/v1/lenders/{lender_id}/submit`

**Request:**
```json
{
  "application_id": "app-uuid-v4",
  "product_id": "prod-uuid-v4",
  "submission_method": "email"
}
```

**Response (202):**
```json
{
  "submission_id": "sub-uuid-v4",
  "status": "pending",
  "message": "Application submitted to lender successfully.",
  "submitted_at": "2026-03-02T11:00:00Z"
}
```

**Errors:**
- `400`: Application does not meet product criteria.
- `404`: Lender or Product not found.
- `503`: Lender submission service unavailable.

---

## Configuration Notes

### Environment Variables

Add the following to `.env.example`:

```bash
# Lender Comparison & Submission
# Default email sender for lender submissions (if SMTP integration is used)
LENDER_SUBMISSION_FROM_EMAIL=noreply@mortgage-system.com

# Timeout for external lender API calls (seconds)
LENDER_API_TIMEOUT=30
```

### Dependencies
- Requires `common.email` for sending submissions.
- Relies on `common.security` for encrypting sensitive lender credentials if API integrations are used.

---

## Changelog Entry

```markdown
## [2026-03-02]
### Added
- Lender Comparison & Submission: New endpoints for managing lenders and products.
- POST /api/v1/lenders/compare: Added logic to match borrower profiles against lender products using OSFI B-20 stress testing.
- POST /api/v1/lenders/{id}/submit: Added functionality to submit applications to lenders.
```