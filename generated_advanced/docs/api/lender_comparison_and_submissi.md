# Lender Comparison & Submission Documentation

## 1. API Documentation

**File:** `docs/api/Lender_Comparison_and_Submission.md`

```markdown
# Lender Comparison & Submission API

This module provides endpoints to manage lending institutions, their specific product guidelines, and the submission of mortgage applications for underwriting.

## Lenders

### GET /api/v1/lenders
Retrieve a list of all active lenders.

**Query Parameters:**
- `is_active` (bool, optional): Filter by active status. Defaults to `true`.
- `type` (str, optional): Filter by lender type (bank, credit_union, monoline, private, mfc).

**Response (200):**
```json
{
  "count": 2,
  "items": [
    {
      "id": 1,
      "name": "First National Bank",
      "type": "bank",
      "is_active": true,
      "logo_url": "https://cdn.example.com/logos/fnb.png",
      "submission_email": "underwriting@fnb.com",
      "notes": "Preferred lender for high-ratio deals"
    }
  ]
}
```

### GET /api/v1/lenders/{id}
Retrieve details for a specific lender.

**Response (200):**
```json
{
  "id": 1,
  "name": "First National Bank",
  "type": "bank",
  "is_active": true,
  "logo_url": "https://cdn.example.com/logos/fnb.png",
  "submission_email": "underwriting@fnb.com",
  "notes": "Preferred lender for high-ratio deals",
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-01-15T10:00:00Z"
}
```

**Errors:**
- 404: Lender not found

---

## Lender Products

### GET /api/v1/lender-products
Retrieve lender products. Supports filtering to find suitable products based on application criteria.

**Query Parameters:**
- `lender_id` (int, optional): Filter by specific lender.
- `mortgage_type` (str, optional): Filter by type (fixed, variable, heloc).
- `min_credit_score` (int, optional): Return products where `min_credit_score` <= value.
- `ltv` (decimal, optional): Return products where `max_ltv` >= value.
- `is_self_employed` (bool, optional): Filter for products allowing self-employment.

**Response (200):**
```json
{
  "count": 1,
  "items": [
    {
      "id": 101,
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
      "allows_gifted_down_payment": true,
      "prepayment_options": "15% + 15% increase"
    }
  ]
}
```

### POST /api/v1/lender-products
Create a new lender product (Admin only).

**Request:**
```json
{
  "lender_id": 1,
  "product_name": "Special 3-Year Variable",
  "mortgage_type": "variable",
  "term_years": 3,
  "rate": "5.10",
  "rate_type": "prime_plus",
  "max_ltv_insured": "80.00",
  "max_ltv_conventional": "80.00",
  "min_credit_score": 700,
  "max_gds": "35.00",
  "max_tds": "42.00"
}
```

**Response (201):**
```json
{
  "id": 102,
  "lender_id": 1,
  "product_name": "Special 3-Year Variable",
  "created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 400: Invalid input data (e.g., LTV > 100%)
- 403: Forbidden (Admin access required)

---

## Comparison & Submission

### POST /api/v1/lender-products/compare
Compare a specific application scenario against all active products to find matches.

**Request:**
```json
{
  "loan_amount": "450000.00",
  "property_value": "500000.00",
  "ltv": "90.00",
  "credit_score": 710,
  "is_self_employed": false,
  "has_rental_income": false,
  "down_payment_source": "savings",
  "mortgage_type": "fixed",
  "term_years": 5
}
```

**Response (200):**
```json
{
  "matches": [
    {
      "lender_product_id": 101,
      "lender_name": "First National Bank",
      "product_name": "5-Year Fixed High-Ratio",
      "rate": "5.29",
      "monthly_payment": "2630.00"
    }
  ],
  "total_matches": 1
}
```

### POST /api/v1/submissions
Submit a mortgage application to a specific lender.

**Request:**
```json
{
  "lender_id": 1,
  "application_id": "app_12345",
  "product_id": 101,
  "submitted_data": {
    "borrower_name_hash": "sha256_hash",
    "income_verification": "verified",
    "credit_report_id": "cr_987"
  }
}
```

**Response (201):**
```json
{
  "id": "sub_999",
  "application_id": "app_12345",
  "lender_id": 1,
  "status": "pending",
  "submitted_at": "2026-03-02T14:35:00Z"
}
```

**Errors:**
- 400: Validation failed (e.g., GDS/TDS exceeds lender limits)
- 404: Lender or Product not found
- 422: Unprocessable Entity (Missing required submission data)
```

## 2. Module README

**File:** `docs/modules/Lender_Comparison_and_Submission.md`

```markdown
# Lender Comparison & Submission Module

## Overview
The Lender Comparison & Submission module serves as the central repository for lender guidelines and the decision engine for matching borrower applications to appropriate mortgage products. It handles the storage of lender-specific criteria (LTV limits, credit score floors, GDS/TDS caps) and manages the secure submission of qualified applications.

## Key Functions

### 1. Product Matching Logic
The `LenderService` includes logic to filter `lender_products` based on borrower attributes:
- **LTV Check:** Compares application Loan-to-Value against `max_ltv_insured` or `max_ltv_conventional`.
- **Credit Score:** Enforces `min_credit_score` requirements.
- **Debt Service Ratios:** Validates application GDS/TDS against product `max_gds` and `max_tds` (OSFI B-20 compliant).
- **Borrower Status:** Checks flags for `allows_self_employed`, `allows_rental_income`, and `allows_gifted_down_payment`.

### 2. Submission Handling
The `SubmissionService` manages the transmission of application data to lenders.
- **Audit Trail:** All submissions are immutable (FINTRAC compliant), recording `created_at` and status changes.
- **Data Formatting:** Formats application data into the specific structure required by the destination `lender_id`.
- **Status Tracking:** Tracks the lifecycle of a submission (Pending, Received, Approved, Rejected).

## Usage Example

### Finding a suitable product
```python
from modules.lender_comparison.services import LenderService

# Initialize service
service = LenderService(db_session)

# Define search criteria
criteria = {
    "ltv": Decimal("90.00"),
    "credit_score": 720,
    "mortgage_type": "fixed",
    "term_years": 5
}

# Find matches
matches = await service.find_matching_products(criteria)

for product in matches:
    print(f"Match: {product.product_name} at {product.rate}%")
```

### Submitting an application
```python
from modules.lender_comparison.services import SubmissionService

service = SubmissionService(db_session)

# Create submission record
submission = await service.submit_application(
    lender_id=1,
    application_id="app_123",
    payload={...} # Sanitized payload
)
```

## Security & Compliance Notes
- **PIPEDA:** Submission payloads must not contain raw SIN or DOB. Use hashed identifiers.
- **OSFI B-20:** The comparison logic respects the qualifying rate stress test implicitly by relying on pre-calculated GDS/TDS ratios passed in the request.
- **CMHC:** Product definitions explicitly separate `max_ltv_insured` vs `max_ltv_conventional`.
```

## 3. Configuration Notes

**File:** `.env.example`

```bash
# ... existing config ...

# Lender Comparison & Submission Configuration
# Default sender email for lender submissions (can be overridden per lender)
LENDER_SUBMISSION_FROM_EMAIL=noreply@mortgage-system.com

# Timeout for external lender API calls (if applicable)
LENDER_API_TIMEOUT_SECONDS=30
```

## 4. Changelog Update

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Lender Comparison & Submission: New module for managing lender repositories and product guidelines.
- Lender Comparison & Submission: API endpoints for listing lenders, filtering products, and submitting applications.
- Lender Comparison & Submission: Logic to match borrower criteria (LTV, Credit Score, GDS/TDS) against lender products.

### Changed
- Updated common/config.py to include lender submission settings.

### Fixed
- N/A
```