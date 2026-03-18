# Lender Comparison & Submission
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Lender Comparison & Submission Module Design

**Module slug:** `lender_comparison`  
**Design document:** `docs/design/lender-comparison-submission.md`  
**Version:** 1.0  
**Last updated:** 2024-06-27

---

## 1. Endpoints

All endpoints are prefixed with `/api/v1`. Authentication is required via JWT (broker role). Rate‑limiting and request‑id correlation are enforced at the API gateway.

### 1.1 `GET /lenders`
List all active lenders.

- **Auth:** authenticated (broker)  
- **Query params:**  
  - `type` (optional, enum: `bank`, `credit_union`, `monoline`, `private`, `mfc`) – filter by lender type.  
  - `is_active` (optional, bool, default=`true`) – include inactive lenders if `false`.  
- **Response 200 OK**  
  ```json
  [
    {
      "id": "uuid",
      "name": "Bank of Montreal",
      "type": "bank",
      "is_active": true,
      "logo_url": "https://cdn.example.com/logos/bmo.png",
      "submission_email": "brokers@bmo.com",
      "notes": "Standard B-20 guidelines apply"
    }
  ]
  ```
- **Error responses**  
  - `401 Unauthorized` – missing or invalid token.  
  - `403 Forbidden` – user lacks broker role.  

---

### 1.2 `GET /lenders/{id}/products`
Fetch all active products for a given lender.

- **Auth:** authenticated (broker)  
- **Path params:** `id` (uuid) – lender identifier.  
- **Query params:**  
  - `mortgage_type` (optional, enum: `fixed`, `variable`, `heloc`).  
  - `effective_date` (optional, date) – filter products valid on this date (default=today).  
- **Response 200 OK**  
  ```json
  {
    "lender_id": "uuid",
    "products": [
      {
        "id": "uuid",
        "product_name": "5‑Year Fixed Closed",
        "mortgage_type": "fixed",
        "term_years": 5,
        "rate": "4.99",
        "rate_type": "discounted",
        "max_ltv_insured": "95.00",
        "max_ltv_conventional": "80.00",
        "max_amortization_insured": 25,
        "max_amortization_conventional": 30,
        "min_credit_score": 680,
        "max_gds": "39.00",
        "max_tds": "44.00",
        "allows_self_employed": true,
        "allows_rental_income": false,
        "allows_gifted_down_payment": true,
        "prepayment_privilege_percent": "20.00",
        "portability": true,
        "assumability": false,
        "is_active": true,
        "effective_date": "2024-06-01",
        "expiry_date": "2024-12-31"
      }
    ]
  }
  ```
- **Error responses**  
  - `404 Not Found` – lender does not exist (error_code: `LENDER_001`).  
  - `401/403` – as above.  

---

### 1.3 `POST /lenders/match`
Run the lender‑matching engine against a submitted mortgage application.

- **Auth:** authenticated (broker)  
- **Request body**  
  ```json
  {
    "application_id": "uuid",           // required
    "credit_score": 720,                // required, int
    "gross_monthly_income": "8500.00",  // required, Decimal
    "monthly_property_tax": "450.00",   // required, Decimal
    "monthly_heating": "150.00",        // required, Decimal
    "monthly_condo_fees": "0.00",       // optional, default "0.00"
    "other_debt_payments": "1200.00",   // required, Decimal
    "loan_amount": "450000.00",         // required, Decimal
    "property_value": "600000.00",      // required, Decimal
    "contract_rate": "4.99",            // required, Decimal
    "is_insured": false,                // required, bool
    "requested_amortization": 25,       // required, int (years)
    "self_employed": false,             // required, bool
    "rental_income": "0.00",            // optional, Decimal
    "gifted_down_payment": "0.00"       // optional, Decimal
  }
  ```
- **Response 200 OK** – ranked list of matching products.  
  ```json
  {
    "matches": [
      {
        "lender_id": "uuid",
        "lender_name": "Bank of Montreal",
        "product_id": "uuid",
        "product_name": "5‑Year Fixed Closed",
        "rate": "4.99",
        "rate_type": "discounted",
        "qualifying_rate": "6.99",          // OSFI stress‑test rate
        "gds": "32.50",                     // calculated GDS (%)
        "tds": "42.10",                     // calculated TDS (%)
        "ltv": "75.00",                     // loan‑to‑value (%)
        "insurance_required": false,
        "insurance_premium_rate": null,
        "eligible": true,
        "condition_flags": [
          "Self‑employed income accepted",
          "Gifted down‑payment allowed"
        ]
      }
    ],
    "ineligible": [
      {
        "lender_id": "uuid",
        "product_id": "uuid",
        "reason": "TDS 45.20% exceeds lender maximum 44.00%"
      }
    ]
  }
  ```
- **Error responses**  
  - `422 Unprocessable Entity` – validation error (error_code: `LENDER_003`). Example: missing required field, negative income.  
  - `404 Not Found` – application not found (error_code: `LENDER_004`).  
  - `409 Conflict` – application already matched or locked (error_code: `LENDER_006`).  

---

### 1.4 `GET /applications/{id}/lender‑matches`
Retrieve previously saved lender matches for an application.

- **Auth:** authenticated (broker) – user must own the application.  
- **Path params:** `id` (uuid) – application identifier.  
- **Query params:**  
  - `status` (optional, enum: `eligible`, `ineligible`) – filter matches.  
- **Response 200 OK** – same shape as `POST /lenders/match`.  
- **Error responses**  
  - `404 Not Found` – application not found (error_code: `LENDER_004`).  
  - `403 Forbidden` – user does not own the application.  

---

### 1.5 `POST /applications/{id}/submissions`
Create a lender submission record (package generation & email trigger).

- **Auth:** authenticated (broker) – user must own the application.  
- **Path params:** `id` (uuid) – application identifier.  
- **Request body**  
  ```json
  {
    "lender_id": "uuid",          // required
    "product_id": "uuid",         // required
    "broker_notes": "Strong co‑signer, quick close",  // optional, string
    "rate_lock_days": 30          // optional, int, default 30
  }
  ```
- **Response 201 Created**  
  ```json
  {
    "submission_id": "uuid",
    "application_id": "uuid",
    "lender_id": "uuid",
    "product_id": "uuid",
    "submitted_by": "uuid",
    "submitted_at": "2024-06-27T14:30:00Z",
    "status": "pending",
    "lender_reference_number": null,
    "lender_conditions": null,
    "approved_rate": null,
    "approved_amount": null,
    "expiry_date": "2024-07-27",
    "broker_notes": "Strong co‑signer, quick close",
    "created_at": "2024-06-27T14:30:00Z",
    "updated_at": "2024-06-27T14:30:00Z"
  }
  ```
- **Error responses**  
  - `422 Unprocessable Entity` – validation error (error_code: `LENDER_003`).  
  - `404 Not Found` – application, lender, or product not found (error_code: `LENDER_001`/`LENDER_002`).  
  - `409 Conflict` – duplicate submission to same lender (error_code: `LENDER_006`).  
  - `403 Forbidden` – user does not own the application.  

---

### 1.6 `GET /applications/{id}/submissions`
List all submissions for an application.

- **Auth:** authenticated (broker) – user must own the application.  
- **Path params:** `id` (uuid) – application identifier.  
- **Query params:**  
  - `status` (optional, enum: `pending`, `approved`, `declined`, `countered`).  
- **Response 200 OK** – array of submission objects (same shape as above).  
- **Error responses** – `404`, `403` as above.  

---

### 1.7 `PUT /applications/{id}/submissions/{sub_id}`
Update a submission status (e.g., lender responds with approval, decline, or counter).

- **Auth:** authenticated (broker) – user must own the application.  
- **Path params:** `id` (uuid) – application identifier; `sub_id` (uuid) – submission identifier.  
- **Request body**  
  ```json
  {
    "status": "approved",         // required, enum: pending/approved/declined/countered
    "lender_reference_number": "BMO‑2024‑12345",  // required if status=approved
    "lender_conditions": "Proof of property insurance required",  // optional
    "approved_rate": "4.89",      // optional, Decimal
    "approved_amount": "450000.00", // optional, Decimal
    "expiry_date": "2024-08-27"   // optional, date
  }
  ```
- **Response 200 OK** – updated submission object.  
- **Error responses**  
  - `422 Unprocessable Entity` – validation error (error_code: `LENDER_003`).  
  - `404 Not Found` – submission not found (error_code: `LENDER_004`).  
  - `409 Conflict` – status transition not allowed (e.g., approved → pending) (error_code: `LENDER_005`).  
  - `403 Forbidden` – user does not own the application.  

---

## 2. Models & Database

### 2.1 `lenders` table
Stores lender metadata.

| Column            | Type          | Constraints                     | Notes                              |
|-------------------|---------------|---------------------------------|------------------------------------|
| `id`              | UUID          | PRIMARY KEY                     |                                    |
| `name`            | VARCHAR(255)  | NOT NULL                        |                                    |
| `type`            | VARCHAR(50)   | NOT NULL                        | Enum: `bank`, `credit_union`, `monoline`, `private`, `mfc` |
| `is_active`       | BOOLEAN       | NOT NULL, DEFAULT true          |                                    |
| `logo_url`        | VARCHAR(500)  | NULLABLE                        | CDN URL                            |
| `submission_email`| VARCHAR(255)  | NULLABLE                        | Email for package delivery         |
| `notes`           | TEXT          | NULLABLE                        | Internal notes (PII encrypted)     |
| `created_at`      | TIMESTAMPTZ   | NOT NULL, DEFAULT NOW()         | Audit field                        |
| `updated_at`      | TIMESTAMPTZ   | NOT NULL, DEFAULT NOW()         | Auto‑updated on change             |

**Indexes:**
- `idx_lenders_active` on (`is_active`)

---

### 2.2 `lender_products` table
Stores product‑level underwriting criteria.

| Column                        | Type          | Constraints                     | Notes                              |
|-------------------------------|---------------|---------------------------------|------------------------------------|
| `id`                          | UUID          | PRIMARY KEY                     |                                    |
| `lender_id`                   | UUID          | NOT NULL, FK → lenders.id       | Cascade on delete restrict         |
| `product_name`                | VARCHAR(255)  | NOT NULL                        |                                    |
| `mortgage_type`               | VARCHAR(50)   | NOT NULL                        | Enum: `fixed`, `variable`, `heloc` |
| `term_years`                  | SMALLINT      | NOT NULL                        |                                    |
| `rate`                        | DECIMAL(6,3)  | NOT NULL                        | Annual rate (%), e.g., 4.990       |
| `rate_type`                   | VARCHAR(50)   | NOT NULL                        | Enum: `posted`, `discounted`, `prime_plus` |
| `max_ltv_insured`             | DECIMAL(5,2)  | NOT NULL                        | Max LTV if insured (%)             |
| `max_ltv_conventional`        | DECIMAL(5,2)  | NOT NULL                        | Max LTV if conventional (%)        |
| `max_amortization_insured`    | SMALLINT      | NOT NULL                        | Years                              |
| `max_amortization_conventional`| SMALLINT      | NOT NULL                        | Years                              |
| `min_credit_score`            | INTEGER       | NOT NULL                        |                                    |
| `max_gds`                     | DECIMAL(5,2)  | NOT NULL                        | GDS limit (%)                      |
| `max_tds`                     | DECIMAL(5,2)  | NOT NULL                        | TDS limit (%)                      |
| `allows_self_employed`        | BOOLEAN       | NOT NULL, DEFAULT false         |                                    |
| `allows_rental_income`        | BOOLEAN       | NOT NULL, DEFAULT false         |                                    |
| `allows_gifted_down_payment`  | BOOLEAN       | NOT NULL, DEFAULT false         |                                    |
| `prepayment_privilege_percent`| DECIMAL(5,2)  | NULLABLE                        | % of original principal            |
| `portability`                 | BOOLEAN       | NOT NULL, DEFAULT false         |                                    |
| `assumability`                | BOOLEAN       | NOT NULL, DEFAULT false         |                                    |
| `is_active`                   | BOOLEAN       | NOT NULL, DEFAULT true          |                                    |
| `effective_date`              | DATE          | NOT NULL                        | Product availability start         |
| `expiry_date`                 | DATE          | NULLABLE                        | Product availability end           |
| `created_at`                  | TIMESTAMPTZ   | NOT NULL, DEFAULT NOW()         | Audit field                        |
| `updated_at`                  | TIMESTAMPTZ   | NOT NULL, DEFAULT NOW()         | Auto‑updated on change             |

**Indexes:**
- `idx_lender_products_lender` on (`lender_id`)
- `idx_lender_products_active` on (`is_active`, `effective_date`, `expiry_date`)
- `idx_lender_products_rate` on (`rate`) – for sorting matches

**Check constraints:**
- `rate >= 0`
- `max_ltv_insured <= 100.00`
- `max_ltv_conventional <= 100.00`
- `max_gds <= 100.00`
- `max_tds <= 100.00`

---

### 2.3 `lender_submissions` table
Tracks each lender submission package.

| Column                  | Type          | Constraints                     | Notes                              |
|-------------------------|---------------|---------------------------------|------------------------------------|
| `id`                    | UUID          | PRIMARY KEY                     |                                    |
| `application_id`        | UUID          | NOT NULL, FK → applications.id  | Cascade on delete restrict         |
| `lender_id`             | UUID          | NOT NULL, FK → lenders.id       | Cascade on delete restrict         |
| `product_id`            | UUID          | NOT NULL, FK → lender_products.id| Cascade on delete restrict         |
| `submitted_by`          | UUID          | NOT NULL, FK → users.id         | Who created the submission         |
| `submitted_at`          | TIMESTAMPTZ   | NOT NULL, DEFAULT NOW()         |                                    |
| `status`                | VARCHAR(50)   | NOT NULL, DEFAULT 'pending'     | Enum: `pending`, `approved`, `declined`, `countered` |
| `lender_reference_number`| VARCHAR(100)  | NULLABLE                        | Lender’s own reference             |
| `lender_conditions`     | TEXT          | NULLABLE                        | Free‑text conditions (PII encrypted)|
| `approved_rate`         | DECIMAL(6,3)  | NULLABLE                        | Final rate offered                 |
| `approved_amount`       | DECIMAL(12,2) | NULLABLE                        | Final loan amount                  |
| `expiry_date`           | DATE          | NULLABLE                        | Rate/product expiry                |
| `notes`                 | TEXT          | NULLABLE                        | Broker notes (PII encrypted)       |
| `created_at`            | TIMESTAMPTZ   | NOT NULL, DEFAULT NOW()         | Audit field (immutable)            |
| `updated_at`            | TIMESTAMPTZ   | NOT NULL, DEFAULT NOW()         | Auto‑updated on change             |

**Indexes:**
- `idx_lender_submissions_application` on (`application_id`)
- `idx_lender_submissions_lender` on (`lender_id`)
- `idx_lender_submissions_status` on (`status`)
- `idx_lender_submissions_submitted_by` on (`submitted_by`)

**Unique constraint:**
- `uq_lender_submission_per_app_lender` on (`application_id`, `lender_id`) – prevents duplicate submissions to the same lender.

**Check constraints:**
- `approved_rate >= 0`
- `approved_amount >= 0`

---

## 3. Business Logic

### 3.1 LenderMatcher Service
**Purpose:** Filter and rank lender products against a borrower’s financial profile.

**Inputs:**
- Application financials (see `POST /lenders/match` request body).
- Lender product catalog (active & effective).

**Algorithm Steps:**

1. **Calculate LTV**  
   ```python
   ltv = (loan_amount / property_value) * 100
   ```
   Use `Decimal` with precision 5,2.

2. **Determine stress‑test qualifying rate (OSFI B‑20)**  
   ```python
   qualifying_rate = max(contract_rate + Decimal('2.00'), Decimal('5.25'))
   ```

3. **Compute GDS & TDS** (using qualifying rate for PITH)  
   ```python
   monthly_rate = qualifying_rate / 100 / 12
   pith = loan_amount * monthly_rate / (1 - (1 + monthly_rate) ** (-amortization_months))
   pith += monthly_property_tax + monthly_heating + monthly_condo_fees

   gds = (pith / gross_monthly_income) * 100
   tds = ((pith + other_debt_payments) / gross_monthly_income) * 100
   ```

4. **CMHC Insurance Check**  
   If `ltv > 80.00` → `insurance_required = True`.  
   Lookup premium tier:
   - 80.01‑85.00% → 2.80%
   - 85.01‑90.00% → 3.10%
   - 90.01‑95.00% → 4.00%

5. **Filter products** (all criteria must pass):
   - `product.is_active = true` AND `effective_date ≤ today ≤ expiry_date`.
   - `credit_score ≥ product.min_credit_score`.
   - `ltv ≤ product.max_ltv_insured` (if insured) OR `ltv ≤ product.max_ltv_conventional`.
   - `gds ≤ product.max_gds`.
   - `tds ≤ product.max_tds`.
   - `requested_amortization ≤ product.max_amortization_*` (based on insured flag).
   - `self_employed = true` → `product.allows_self_employed = true`.
   - `rental_income > 0` → `product.allows_rental_income = true`.
   - `gifted_down_payment > 0` → `product.allows_gifted_down_payment = true`.

6. **Rank matches** – sort by `product.rate` ascending (lowest rate first).

7. **Flag conditions** – for each match, populate `condition_flags` with human‑readable strings describing lender‑specific features (e.g., “Pre‑payment privilege up to 20%”).

8. **Log auditable calculation** – JSON blob with all intermediate values (LTV, GDS, TDS, qualifying_rate, insurance premium) attached to `correlation_id`.

**Output:** Ranked list of eligible products + separate list of ineligible products with reason.

---

### 3.2 SubmissionPackageGenerator Service
**Purpose:** Compile a complete, regulator‑ready submission package.

**Components:**

1. **Application Summary** – borrower(s) name, DOB (encrypted), SIN (hashed), contact info, property address, purchase price, loan amount, LTV, amortization, requested product.
2. **Underwriting Results** – GDS, TDS, LTV, credit score, stress‑test rate, insurance required, premium rate, eligibility flags.
3. **Document Manifest** – list of all uploaded documents (ID, income proof, property appraisal) with document IDs, upload timestamps, and verification status.
4. **FINTRAC Section** – identity verification logs (timestamp, method, outcome), any transaction > CAD $10,000 flagged with transaction type, source of funds declaration.
5. **Broker Notes** – free‑text notes (encrypted) from the broker.

**Delivery:**  
- Generate a PDF (or standardized XML) and email to `lender.submission_email`.  
- Store a copy in secure object storage (S3‑compatible) with metadata linking to `lender_submissions.id`.  
- Log the event with `correlation_id` (exclude PII).

---

### 3.3 Rate Lock Mechanism (Future)
- Add `rate_lock_expiry` column to `lender_submissions`.  
- When a submission is created, set `expiry_date = now + rate_lock_days`.  
- A scheduled job will mark submissions as `expired` if `expiry_date < today`.  
- Lender responses after expiry require re‑pricing via `LenderMatcher`.

---

### 3.4 Automated Rate Comparison Reporting (Future)
- Daily batch job queries `lender_products` for active rates.  
- Generates a report (CSV/PDF) showing best available rates per product type, LTV tier, and credit score band.  
- Stores report in secure storage and notifies brokers via email.

---

## 4. Migrations

### 4.1 New Tables
Create the following tables via Alembic (revision `lender_comparison_001`):

- `lenders`
- `lender_products`
- `lender_submissions`

### 4.2 Indexes
Add indexes listed in the **Models & Database** section for query performance.

### 4.3 Foreign Key Constraints
- `lender_products.lender_id` → `lenders.id` (ON DELETE RESTRICT).  
- `lender_submissions.application_id` → `applications.id` (ON DELETE RESTRICT).  
- `lender_submissions.lender_id` → `lenders.id` (ON DELETE RESTRICT).  
- `lender_submissions.product_id` → `lender_products.id` (ON DELETE RESTRICT).  
- `lender_submissions.submitted_by` → `users.id` (ON DELETE RESTRICT).

### 4.4 Seed Data (Initial Migration)
Insert the “Big 5” Canadian banks and a representative set of products:

- **Lenders:** RBC, TD, Scotiabank, BMO, CIBC (type=`bank`, `is_active=true`).  
- **Products:** 5‑year fixed, 3‑year fixed, 5‑year variable, HELOC (rate, max LTV, GDS/TDS limits per OSFI B‑20).  

Seed data is idempotent (INSERT … ON CONFLICT DO NOTHING).

---

## 5. Security & Compliance

### 5.1 OSFI B‑20
- **Stress‑test rate:** All GDS/TDS calculations must use `qualifying_rate = max(contract_rate + 2%, 5.25%)`.  
- **Hard limits:** GDS ≤ 39%, TDS ≤ 44%. If any product exceeds these limits, mark as ineligible.  
- **Audit logging:** Log the full calculation breakdown (LTV, GDS, TDS, qualifying_rate) with `correlation_id` for regulator review.

### 5.2 FINTRAC
- **Immutable audit trail:** `lender_submissions` records are insert‑only; `updated_at` tracks changes but rows are never deleted. Retain for 5 years.  
- **Identity verification:** Log verification events (timestamp, method, outcome) in a separate `identity_verifications` table (not detailed here).  
- **Large transaction flag:** If `loan_amount > 10000`, set `transaction_type` field (e.g., `mortgage_origination`) in the FINTRAC report payload.  
- **Reporting:** Monthly automated FINTRAC report generation (out of scope for this module).

### 5.3 CMHC
- **Insurance logic:** When `ltv > 80%`, set `insurance_required = True` and compute premium using tiered rates (2.80%, 3.10%, 4.00%). Store premium amount in `lender_submissions` (optional field).  
- **Precision:** Use `Decimal` for all financial values to avoid rounding errors.

### 5.4 PIPEDA
- **Encryption at rest:** Any free‑text fields that may contain PII (`notes`, `lender_conditions`) must be encrypted using AES‑256 via `common/security.encrypt_pii()`.  
- **Data minimization:** Only collect fields required for underwriting; avoid storing SIN/DOB in this module.  
- **No logging of sensitive data:** Ensure structlog filters exclude `notes`, `lender_conditions`, and any borrower PII.

### 5.5 Authentication & Authorization
- All endpoints require a valid JWT (`broker` scope).  
- `GET /applications/{id}/*` endpoints enforce ownership: `submitted_by` must match the JWT `sub` claim (or user must have `admin` role).  
- Admin role can view all submissions for reporting.

---

## 6. Error Codes & HTTP Responses

| Exception Class                | HTTP Status | Error Code | Message Pattern                                           |
|--------------------------------|-------------|------------|-----------------------------------------------------------|
| `LenderNotFoundError`          | 404         | LENDER_001 | "Lender {id} not found"                                   |
| `LenderProductNotFoundError`   | 404         | LENDER_002 | "Product {id} not found"                                  |
| `LenderMatchValidationError`   | 422         | LENDER_003 | "{field}: {reason}"                                       |
| `LenderSubmissionNotFoundError`| 404         | LENDER_004 | "Submission {sub_id} not found"                           |
| `LenderSubmissionStatusError`  | 409         | LENDER_005 | "Status transition {old} → {new} not allowed"             |
| `LenderSubmissionConflictError`| 409         | LENDER_006 | "Duplicate submission to lender {lender_id}"              |
| `ApplicationNotFoundError`     | 404         | LENDER_007 | "Application {id} not found"                              |
| `UnauthorizedAccessError`      | 403         | LENDER_008 | "User does not own this resource"                         |

**Error Response Body (consistent across all errors):**
```json
{
  "detail": "Lender 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "LENDER_001",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

## 7. Future Considerations & Open Questions

| Item | Description | Recommendation |
|------|-------------|----------------|
| **Rate update frequency** | How often are lender rates refreshed? | Start with daily batch feed; later integrate real‑time API from rate aggregators. |
| **Lender submission format** | Standardize PDF vs. XML vs. JSON. | Define a modular `PackageFormatter` interface; default to PDF for human review. |
| **Rate lock mechanism** | Lock rate for 30‑45 days; handle expiry. | Add `rate_lock_expiry` column and a cron job to expire submissions. |
| **Automated rate comparison reporting** | Daily/weekly broker newsletter. | Build a separate `reporting` module that queries `lender_products` and emails brokers. |
| **Seed data maintenance** | Keep Big‑5 products up‑to‑date. | Create a CLI command `uv run manage.py seed_lenders` that reads from a YAML file under version control. |

---

**End of Design Document**