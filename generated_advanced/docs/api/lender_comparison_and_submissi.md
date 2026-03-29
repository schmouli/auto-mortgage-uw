# Lender Comparison & Submission API

## Module Overview

The **Lender Comparison & Submission** module manages the repository of mortgage lenders and their specific product offerings. It provides the logic to match borrower applications against lender criteria (LTV, GDS/TDS, credit score, employment type) and handles the submission of qualified applications to lenders via email integration.

### Key Functions
- **Product Matching:** Filters `lender_products` based on OSFI B-20 compliance (GDS/TDS limits) and specific lender underwriting guidelines (e.g., self-employment restrictions, rental income allowances).
- **Eligibility Verification:** Ensures `max_ltv` and `max_amortization` constraints are met per product tier (Insured vs. Conventional).
- **Submission Handling:** Facilitates the secure transmission of application data to `submission_email` endpoints defined in the lender registry.

### Usage Example
1.  **Compare:** Client inputs borrower details (income, debts, property value) -> `POST /api/v1/lender-comparison`.
2.  **Select:** System returns list of eligible products with rates.
3.  **Submit:** Broker selects a product -> `POST /api/v1/lender-submission`.

---

## Configuration Notes

Add the following environment variables to your `.env` file to enable the submission functionality:

```bash
# Lender Comparison & Submission Configuration
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@mortgage-system.com
SMTP_PASSWORD=secure_password
SUBMISSION_FROM_EMAIL=noreply@mortgage-system.com
DEFAULT_QUALIFYING_RATE=5.25
```

---

## API Endpoints

### POST /api/v1/lender-comparison

Compares a borrower's financial profile against all active lender products to find eligible matches.

**Request:**
```json
{
  "loan_amount": "450000.00",
  "property_value": "500000.00",
  "mortgage_type": "fixed",
  "term_years": 5,
  "credit_score": 720,
  "annual_income": "120000.00",
  "monthly_property_tax": "300.00",
  "monthly_heating": "150.00",
  "monthly_debts": "500.00",
  "is_self_employed": false,
  "down_payment_source": "savings",
  "is_insured": true
}
```

**Response (200):**
```json
{
  "matches": [
    {
      "lender_id": 1,
      "lender_name": "First National Bank",
      "product_id": 10,
      "product_name": "5-Year Fixed High-Ratio",
      "rate": "4.89",
      "rate_type": "discounted",
      "max_amortization_months": 300,
      "monthly_payment": "2581.45",
      "gds": "28.5",
      "tds": "32.1"
    }
  ],
  "ineligible_reasons": []
}
```

**Errors:**
- `400`: Invalid financial input (negative values, zero income).
- `422`: Validation error (e.g., missing required field).

---

### POST /api/v1/lender-submission

Submits a qualified application to a specific lender's underwriting email address.

**Request:**
```json
{
  "application_id": "uuid-v4-string",
  "lender_product_id": 10,
  "broker_id": 5
}
```

**Response (202):**
```json
{
  "submission_id": "sub_uuid-v4",
  "status": "pending",
  "submitted_at": "2026-03-02T14:30:00Z",
  "lender_email": "underwriting@firstnational.com",
  "message": "Application submitted successfully to First National Bank"
}
```

**Errors:**
- `404`: Lender product or application not found.
- `400`: Application does not meet product eligibility criteria (re-validation failed).
- `500`: Failed to send email via SMTP.

---

### GET /api/v1/lenders

Retrieves a list of all active lenders.

**Query Parameters:**
- `is_active` (boolean, optional): Filter by active status. Defaults to `true`.

**Response (200):**
```json
[
  {
    "id": 1,
    "name": "First National Bank",
    "type": "bank",
    "is_active": true,
    "logo_url": "https://cdn.example.com/logos/fnb.png",
    "notes": "Preferred partner for high-ratio deals"
  }
]
```

---

### GET /api/v1/lender-products

Retrieves available mortgage products, filterable by lender or mortgage type.

**Query Parameters:**
- `lender_id` (integer, optional): Filter by specific lender.
- `mortgage_type` (string, optional): `fixed`, `variable`, or `heloc`.

**Response (200):**
```json
[
  {
    "id": 10,
    "lender_id": 1,
    "product_name": "5-Year Fixed High-Ratio",
    "mortgage_type": "fixed",
    "term_years": 5,
    "rate": "4.89",
    "rate_type": "discounted",
    "max_ltv_insured": "95.00",
    "max_ltv_conventional": "80.00",
    "max_amortization_insured": 300,
    "max_amortization_conventional": 360,
    "min_credit_score": 680,
    "allows_self_employed": true,
    "allows_rental_income": true
  }
]
```

---

### POST /api/v1/lenders

Creates a new lender entry (Admin only).

**Request:**
```json
{
  "name": "Maple Credit Union",
  "type": "credit_union",
  "submission_email": "deals@maplecredit.ca",
  "notes": "Regional focus, Ontario only"
}
```

**Response (201):**
```json
{
  "id": 2,
  "name": "Maple Credit Union",
  "type": "credit_union",
  "is_active": true,
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `400`: Invalid lender type.
- `401`: Not authenticated (Admin required).
- `403`: Permission denied.