# Design: Lender Comparison & Submission
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Design Plan: Lender Comparison & Submission Module

**Feature Slug:** `lender-comparison-submission`  
**Module Path:** `modules/lender/`  
**Target File:** `docs/design/lender-comparison-submission.md`

---

## 1. Endpoints

### `GET /api/v1/lenders`
List all active lenders with optional filtering.

**Query Parameters:**
- `is_active` (boolean, optional, default: `true`) - Filter by active status
- `lender_type` (enum: bank/credit_union/monoline/private/mfc, optional) - Filter by lender type

**Response Schema (200 OK):**
```json
{
  "lenders": [
    {
      "id": "uuid",
      "name": "string",
      "type": "bank",
      "logo_url": "string|null",
      "submission_email": "string|null",
      "notes": "string|null",
      "is_active": "boolean",
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ],
  "total": "integer",
  "page": "integer",
  "page_size": "integer"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or missing JWT token
- `403 Forbidden` - User lacks `lender:read` permission

**Authentication:** Authenticated user with `lender:read` scope.

---

### `GET /api/v1/lenders/{id}/products`
Retrieve all active products for a specific lender.

**Path Parameters:**
- `id` (uuid, required) - Lender ID

**Query Parameters:**
- `is_active` (boolean, optional, default: `true`)
- `mortgage_type` (enum: fixed/variable/heloc, optional)

**Response Schema (200 OK):**
```json
{
  "lender_id": "uuid",
  "lender_name": "string",
  "products": [
    {
      "id": "uuid",
      "product_name": "string",
      "mortgage_type": "fixed",
      "term_years": "integer",
      "rate": "decimal(5,3)",
      "rate_type": "discounted",
      "max_ltv_insured": "decimal(5,2)",
      "max_ltv_conventional": "decimal(5,2)",
      "max_amortization_insured": "integer",
      "max_amortization_conventional": "integer",
      "min_credit_score": "integer",
      "max_gds": "decimal(5,2)",
      "max_tds": "decimal(5,2)",
      "allows_self_employed": "boolean",
      "allows_rental_income": "boolean",
      "allows_gifted_down_payment": "boolean",
      "prepayment_privilege_percent": "decimal(5,2)|null",
      "portability": "boolean",
      "assumability": "boolean",
      "is_active": "boolean",
      "effective_date": "date",
      "expiry_date": "date|null"
    }
  ]
}
```

**Error Responses:**
- `404 Not Found` - `LENDER_001`: "Lender not found"
- `401 Unauthorized` - Invalid JWT
- `403 Forbidden` - Missing `lender:read` scope

---

### `POST /api/v1/lenders/match`
Match lenders to a mortgage application based on underwriting criteria.

**Request Body Schema:**
```json
{
  "application_id": "uuid (required)",
  "filters": {
    "mortgage_type": "enum: fixed/variable/heloc | null",
    "min_term_years": "integer | null",
    "max_term_years": "integer | null",
    "include_inactive": "boolean (default: false)"
  }
}
```

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "matches": [
    {
      "rank": "integer",
      "product": {
        "id": "uuid",
        "lender_id": "uuid",
        "lender_name": "string",
        "product_name": "string",
        "rate": "decimal(5,3)",
        "rate_type": "discounted",
        "term_years": "integer",
        "mortgage_type": "fixed"
      },
      "eligibility": {
        "ltv_ok": "boolean",
        "gds_ok": "boolean",
        "tds_ok": "boolean",
        "credit_score_ok": "boolean",
        "self_employed_ok": "boolean",
        "rental_income_ok": "boolean",
        "gifted_down_payment_ok": "boolean"
      },
      "flags": ["string"],
      "match_score": "decimal(5,2)"
    }
  ],
  "total_matches": "integer"
}
```

**Error Responses:**
- `404 Not Found` - `LENDER_006`: "Application not found"
- `422 Unprocessable Entity` - `LENDER_004`: "Application missing required UW data: {field}"
- `401 Unauthorized` - Invalid JWT
- `403 Forbidden` - User not authorized for application

**OSFI B-20 Compliance:** Service must re-calculate GDS/TDS with stress test (qualifying_rate = max(contract_rate + 2%, 5.25%)) and log full breakdown.

---

### `GET /api/v1/applications/{id}/lender-matches`
Retrieve saved lender matches for an application.

**Path Parameters:**
- `id` (uuid, required) - Application ID

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "matches": [
    {
      "match_id": "uuid",
      "product_id": "uuid",
      "lender_id": "uuid",
      "rank": "integer",
      "created_at": "datetime"
    }
  ]
}
```

**Error Responses:**
- `404 Not Found` - `LENDER_006`: "Application not found"
- `401 Unauthorized` - Invalid JWT
- `403 Forbidden` - User not authorized for application

---

### `POST /api/v1/applications/{id}/submissions`
Create a lender submission record.

**Path Parameters:**
- `id` (uuid, required) - Application ID

**Request Body Schema:**
```json
{
  "lender_id": "uuid (required)",
  "product_id": "uuid (required)",
  "notes": "string (optional, max 2000 chars)"
}
```

**Response Schema (201 Created):**
```json
{
  "submission_id": "uuid",
  "application_id": "uuid",
  "lender_id": "uuid",
  "product_id": "uuid",
  "status": "pending",
  "submitted_by": "uuid",
  "submitted_at": "datetime",
  "lender_reference_number": "string|null",
  "notes": "string|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Error Responses:**
- `404 Not Found` - `LENDER_001`: "Lender not found" or `LENDER_002`: "Product not found"
- `409 Conflict` - `LENDER_005`: "Active submission already exists for this lender and application"
- `422 Unprocessable Entity` - `LENDER_004`: "Product not eligible: {reason}"
- `401 Unauthorized` - Invalid JWT
- `403 Forbidden` - User lacks `submission:create` scope

**FINTRAC Trigger:** If application.loan_amount > CAD 10,000, log submission with transaction_type = "mortgage_application" to FINTRAC audit table.

---

### `GET /api/v1/applications/{id}/submissions`
List all submissions for an application.

**Path Parameters:**
- `id` (uuid, required) - Application ID

**Query Parameters:**
- `status` (enum: pending/approved/declined/countered, optional)
- `lender_id` (uuid, optional)

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "submissions": [
    {
      "id": "uuid",
      "lender_id": "uuid",
      "lender_name": "string",
      "product_id": "uuid",
      "product_name": "string",
      "status": "pending",
      "submitted_by": "uuid",
      "submitted_at": "datetime",
      "lender_reference_number": "string|null",
      "approved_rate": "decimal(5,3)|null",
      "approved_amount": "decimal(12,2)|null",
      "expiry_date": "date|null",
      "notes": "string|null",
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ]
}
```

**Error Responses:**
- `404 Not Found` - `LENDER_006`: "Application not found"
- `401 Unauthorized` - Invalid JWT
- `403 Forbidden` - User not authorized for application

---

### `PUT /api/v1/applications/{id}/submissions/{sub_id}`
Update submission status and lender response details.

**Path Parameters:**
- `id` (uuid, required) - Application ID
- `sub_id` (uuid, required) - Submission ID

**Request Body Schema:**
```json
{
  "status": "enum: pending/approved/declined/countered (required)",
  "lender_reference_number": "string (optional)",
  "lender_conditions": "json|null",
  "approved_rate": "decimal(5,3)|null",
  "approved_amount": "decimal(12,2)|null",
  "expiry_date": "date|null",
  "notes": "string (optional, max 2000 chars)"
}
```

**Response Schema (200 OK):**
```json
{
  "id": "uuid",
  "application_id": "uuid",
  "lender_id": "uuid",
  "product_id": "uuid",
  "status": "approved",
  "submitted_by": "uuid",
  "submitted_at": "datetime",
  "lender_reference_number": "string|null",
  "lender_conditions": "json|null",
  "approved_rate": "decimal(5,3)",
  "approved_amount": "decimal(12,2)",
  "expiry_date": "date",
  "notes": "string|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Error Responses:**
- `404 Not Found` - `LENDER_003`: "Submission not found"
- `409 Conflict` - `LENDER_005`: "Invalid status transition: {from} → {to}"
- `422 Unprocessable Entity` - `LENDER_004`: "Approved rate missing for approved status"
- `401 Unauthorized` - Invalid JWT
- `403 Forbidden` - User not authorized for application

**State Machine Enforcement:** Only valid transitions allowed:
- `pending` → `approved|declined|countered`
- `countered` → `approved|declined`

---

## 2. Models & Database

### `Lender` Model
**Table:** `lenders`

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `UUID` | PRIMARY KEY | - |
| `name` | `VARCHAR(255)` | NOT NULL, UNIQUE | `idx_lenders_name` |
| `type` | `VARCHAR(50)` | NOT NULL, CHECK IN ('bank','credit_union','monoline','private','mfc') | `idx_lenders_type` |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT true | `idx_lenders_active` |
| `logo_url` | `VARCHAR(500)` | NULL | - |
| `submission_email` | `VARCHAR(255)` | NULL | - |
| `notes` | `TEXT` | NULL | - |
| `created_at` | `TIMESTAMP` | NOT NULL, DEFAULT NOW() | - |
| `updated_at` | `TIMESTAMP` | NOT NULL, DEFAULT NOW() | - |

**Relationships:**
- One-to-many: `products` → `LenderProduct.lender_id`

**Triggers:**
- `updated_at` auto-update trigger

---

### `LenderProduct` Model
**Table:** `lender_products`

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `UUID` | PRIMARY KEY | - |
| `lender_id` | `UUID` | NOT NULL, FK(lenders.id) ON DELETE CASCADE | `idx_lender_products_lender_id` |
| `product_name` | `VARCHAR(255)` | NOT NULL | `idx_lender_products_name` |
| `mortgage_type` | `VARCHAR(50)` | NOT NULL, CHECK IN ('fixed','variable','heloc') | `idx_lender_products_mortgage_type` |
| `term_years` | `INTEGER` | NOT NULL, CHECK > 0 | `idx_lender_products_term` |
| `rate` | `DECIMAL(5,3)` | NOT NULL, CHECK >= 0 | `idx_lender_products_rate` |
| `rate_type` | `VARCHAR(50)` | NOT NULL, CHECK IN ('posted','discounted','prime_plus') | - |
| `max_ltv_insured` | `DECIMAL(5,2)` | NOT NULL, CHECK 0-100 | - |
| `max_ltv_conventional` | `DECIMAL(5,2)` | NOT NULL, CHECK 0-100 | - |
| `max_amortization_insured` | `INTEGER` | NOT NULL, CHECK 5-40 | - |
| `max_amortization_conventional` | `INTEGER` | NOT NULL, CHECK 5-40 | - |
| `min_credit_score` | `INTEGER` | NOT NULL, CHECK 300-900 | `idx_lender_products_min_score` |
| `max_gds` | `DECIMAL(5,2)` | NOT NULL, CHECK 0-100 | - |
| `max_tds` | `DECIMAL(5,2)` | NOT NULL, CHECK 0-100 | - |
| `allows_self_employed` | `BOOLEAN` | NOT NULL, DEFAULT false | `idx_lender_products_self_employed` |
| `allows_rental_income` | `BOOLEAN` | NOT NULL, DEFAULT false | - |
| `allows_gifted_down_payment` | `BOOLEAN` | NOT NULL, DEFAULT false | - |
| `prepayment_privilege_percent` | `DECIMAL(5,2)` | NULL, CHECK 0-100 | - |
| `portability` | `BOOLEAN` | NOT NULL, DEFAULT false | - |
| `assumability` | `BOOLEAN` | NOT NULL, DEFAULT false | - |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT true | `idx_lender_products_active` |
| `effective_date` | `DATE` | NOT NULL | `idx_lender_products_effective` |
| `expiry_date` | `DATE` | NULL | `idx_lender_products_expiry` |
| `created_at` | `TIMESTAMP` | NOT NULL, DEFAULT NOW() | - |
| `updated_at` | `TIMESTAMP` | NOT NULL, DEFAULT NOW() | - |

**Composite Indexes:**
- `idx_lender_products_filters` ON (`is_active`, `mortgage_type`, `min_credit_score`, `max_gds`, `max_tds`)
- `idx_lender_products_rate_match` ON (`rate`, `is_active`) WHERE `expiry_date` IS NULL OR `expiry_date` > CURRENT_DATE

**Relationships:**
- Many-to-one: `lender` → `Lender`
- One-to-many: `submissions` → `LenderSubmission.product_id`

**Check Constraints:**
- `max_ltv_insured > max_ltv_conventional` (insured allows higher LTV)

---

### `LenderSubmission` Model
**Table:** `lender_submissions`

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `UUID` | PRIMARY KEY | - |
| `application_id` | `UUID` | NOT NULL, FK(applications.id) ON DELETE CASCADE | `idx_lender_submissions_app_id` |
| `lender_id` | `UUID` | NOT NULL, FK(lenders.id) ON DELETE RESTRICT | `idx_lender_submissions_lender_id` |
| `product_id` | `UUID` | NOT NULL, FK(lender_products.id) ON DELETE RESTRICT | `idx_lender_submissions_product_id` |
| `submitted_by` | `UUID` | NOT NULL, FK(users.id) ON DELETE RESTRICT | `idx_lender_submissions_submitted_by` |
| `submitted_at` | `TIMESTAMP` | NOT NULL, DEFAULT NOW() | `idx_lender_submissions_submitted_at` |
| `status` | `VARCHAR(50)` | NOT NULL, CHECK IN ('pending','approved','declined','countered'), DEFAULT 'pending' | `idx_lender_submissions_status` |
| `lender_reference_number` | `VARCHAR(100)` | NULL | `idx_lender_submissions_ref` |
| `lender_conditions` | `JSONB` | NULL | - |
| `approved_rate` | `DECIMAL(5,3)` | NULL, CHECK >= 0 | - |
| `approved_amount` | `DECIMAL(12,2)` | NULL, CHECK >= 0 | - |
| `expiry_date` | `DATE` | NULL | `idx_lender_submissions_expiry` |
| `notes` | `TEXT` | NULL | - |
| `created_at` | `TIMESTAMP` | NOT NULL, DEFAULT NOW() | - |
| `updated_at` | `TIMESTAMP` | NOT NULL, DEFAULT NOW() | - |

**Composite Indexes:**
- `idx_lender_submissions_app_status` ON (`application_id`, `status`)
- `idx_lender_submissions_lender_status` ON (`lender_id`, `status`)

**Relationships:**
- Many-to-one: `application` → `Application`
- Many-to-one: `lender` → `Lender`
- Many-to-one: `product` → `LenderProduct`
- Many-to-one: `submitted_by_user` → `User`

**Triggers:**
- `updated_at` auto-update trigger
- Insert trigger: log to `audit_log` table for FINTRAC compliance

---

## 3. Business Logic

### `LenderMatcher` Service
**Algorithm Specification:**

```python
async def match_lenders(
    application_id: UUID,
    filters: LenderMatchFilters | None = None
) -> list[LenderMatchResult]:
    """
    1. Fetch application with:
       - property_value (Decimal)
       - loan_amount (Decimal)
       - gross_monthly_income (Decimal)
       - monthly_property_tax (Decimal)
       - monthly_heating (Decimal)
       - monthly_condo_fees (Decimal)
       - other_debt_payments (Decimal)
       - credit_score (int)
       - income_type (enum)
       - down_payment_source (list)
       - is_rental_property (bool)
    
    2. Calculate key ratios:
       ltv = loan_amount / property_value
       is_insured = ltv > Decimal('0.80')
       
       # OSFI B-20 Stress Test
       qualifying_rate = max(product_rate + Decimal('0.02'), Decimal('0.0525'))
       monthly_payment = calculate_pmt(qualifying_rate, amortization, loan_amount)
       
       gds = (monthly_payment + monthly_property_tax + monthly_heating + monthly_condo_fees) / gross_monthly_income
       tds = (gds_numerator + other_debt_payments) / gross_monthly_income
    
    3. Build query filters:
       - is_active = true
       - effective_date <= today
       - expiry_date IS NULL OR expiry_date >= today
       - min_credit_score <= application.credit_score
       - max_gds >= application.gds
       - max_tds >= application.tds
       - If is_insured: max_ltv_insured >= ltv
         Else: max_ltv_conventional >= ltv
       - If income_type == 'self_employed': allows_self_employed = true
       - If is_rental_property: allows_rental_income = true
       - If 'gift' in down_payment_source: allows_gifted_down_payment = true
    
    4. Sort results by rate ASC (lowest first)
    
    5. Calculate match_score (0-100):
       score = 100
       if ltv > product.max_ltv_conventional * 0.95: score -= 10
       if application.credit_score < product.min_credit_score + 20: score -= 5
       if gds > product.max_gds * 0.95: score -= 10
       if tds > product.max_tds * 0.95: score -= 15
    
    6. Log full calculation breakdown with correlation_id for audit
    """
```

**Flags Generated:**
- `high_ltv_risk`: LTV > 90%
- `borderline_gds`: GDS within 2% of product limit
- `borderline_tds`: TDS within 2% of product limit
- `credit_score_margin`: Score within 30 points of minimum
- `rate_premium`: Rate > prime + 2%

---

### `SubmissionPackageGenerator` Service
**Package Compilation Flow:**

```python
async def generate_submission_package(
    application_id: UUID,
    lender_id: UUID,
    product_id: UUID
) -> UUID:
    """
    1. Fetch and redact application data:
       - Remove: SIN (show last 4 only), DOB, bank account numbers
       - Encrypt: Full SIN, DOB, banking details using AES-256
    
    2. Compile underwriting results:
       - Original GDS/TDS calculations
       - OSFI stress test calculations with qualifying_rate
       - CMHC insurance determination (LTV > 80%)
       - Credit summary (score, tradelines, no PII)
    
    3. Generate document checklist:
       - Income verification docs based on income_type
       - Property appraisal if LTV > 80%
       - Gift letter if down_payment_source includes gift
    
    4. FINTRAC check:
       - If loan_amount >= 10000: generate FINTRAC report snippet
       - Log transaction to audit_log with type 'mortgage_submission'
    
    5. Create structured JSON package:
       {
         "application_summary": { ...redacted... },
         "underwriting_results": {
           "gds": "decimal",
           "tds": "decimal",
           "stress_test_rate": "decimal",
           "insurance_required": "bool",
           "insurance_premium": "decimal|null"
         },
         "documents": [...],
         "fintrac_report": {...}|null,
         "broker_notes": "string"
       }
    
    6. Store in document_storage (S3 compatible) with UUID key
    7. Return package_id for reference
    """
```

---

### State Machine for Submissions

```
pending ──► approved
   │
   ├──► declined
   │
   └──► countered ──► approved
            │
            └──► declined
```

**Transition Rules:**
- Only `pending` → `approved|declined|countered` allowed
- Only `countered` → `approved|declined` allowed
- `approved_rate` and `approved_amount` required when status = `approved`
- `lender_conditions` required when status = `countered`
- `expiry_date` automatically set to 90 days from approval (configurable)

---

## 4. Migrations

### New Tables
```sql
-- Table: lenders
CREATE TABLE lenders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    type VARCHAR(50) NOT NULL CHECK (type IN ('bank','credit_union','monoline','private','mfc')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    logo_url VARCHAR(500),
    submission_email VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_lenders_type ON lenders(type);
CREATE INDEX idx_lenders_active ON lenders(is_active) WHERE is_active = true;

-- Table: lender_products
CREATE TABLE lender_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lender_id UUID NOT NULL REFERENCES lenders(id) ON DELETE CASCADE,
    product_name VARCHAR(255) NOT NULL,
    mortgage_type VARCHAR(50) NOT NULL CHECK (mortgage_type IN ('fixed','variable','heloc')),
    term_years INTEGER NOT NULL CHECK (term_years > 0),
    rate DECIMAL(5,3) NOT NULL CHECK (rate >= 0),
    rate_type VARCHAR(50) NOT NULL CHECK (rate_type IN ('posted','discounted','prime_plus')),
    max_ltv_insured DECIMAL(5,2) NOT NULL CHECK (max_ltv_insured BETWEEN 0 AND 100),
    max_ltv_conventional DECIMAL(5,2) NOT NULL CHECK (max_ltv_conventional BETWEEN 0 AND 100),
    max_amortization_insured INTEGER NOT NULL CHECK (max_amortization_insured BETWEEN 5 AND 40),
    max_amortization_conventional INTEGER NOT NULL CHECK (max_amortization_conventional BETWEEN 5 AND 40),
    min_credit_score INTEGER NOT NULL CHECK (min_credit_score BETWEEN 300 AND 900),
    max_gds DECIMAL(5,2) NOT NULL CHECK (max_gds BETWEEN 0 AND 100),
    max_tds DECIMAL(5,2) NOT NULL CHECK (max_tds BETWEEN 0 AND 100),
    allows_self_employed BOOLEAN NOT NULL DEFAULT false,
    allows_rental_income BOOLEAN NOT NULL DEFAULT false,
    allows_gifted_down_payment BOOLEAN NOT NULL DEFAULT false,
    prepayment_privilege_percent DECIMAL(5,2) CHECK (prepayment_privilege_percent BETWEEN 0 AND 100),
    portability BOOLEAN NOT NULL DEFAULT false,
    assumability BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    effective_date DATE NOT NULL,
    expiry_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_ltv_order CHECK (max_ltv_insured > max_ltv_conventional)
);

CREATE INDEX idx_lender_products_lender_id ON lender_products(lender_id);
CREATE INDEX idx_lender_products_active ON lender_products(is_active) WHERE is_active = true;
CREATE INDEX idx_lender_products_mortgage_type ON lender_products(mortgage_type);
CREATE INDEX idx_lender_products_rate ON lender_products(rate);
CREATE INDEX idx_lender_products_filters ON lender_products(is_active, mortgage_type, min_credit_score, max_gds, max_tds);
CREATE INDEX idx_lender_products_rate_match ON lender_products(rate, is_active) WHERE expiry_date IS NULL OR expiry_date > CURRENT_DATE;

-- Table: lender_submissions
CREATE TABLE lender_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    lender_id UUID NOT NULL REFERENCES lenders(id) ON DELETE RESTRICT,
    product_id UUID NOT NULL REFERENCES lender_products(id) ON DELETE RESTRICT,
    submitted_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    submitted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','declined','countered')),
    lender_reference_number VARCHAR(100),
    lender_conditions JSONB,
    approved_rate DECIMAL(5,3) CHECK (approved_rate >= 0),
    approved_amount DECIMAL(12,2) CHECK (approved_amount >= 0),
    expiry_date DATE,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_lender_submissions_app_id ON lender_submissions(application_id);
CREATE INDEX idx_lender_submissions_lender_id ON lender_submissions(lender_id);
CREATE INDEX idx_lender_submissions_status ON lender_submissions(status);
CREATE INDEX idx_lender_submissions_submitted_at ON lender_submissions(submitted_at DESC);
CREATE INDEX idx_lender_submissions_app_status ON lender_submissions(application_id, status);
CREATE INDEX idx_lender_submissions_lender_status ON lender_submissions(lender_id, status);
CREATE INDEX idx_lender_submissions_ref ON lender_submissions(lender_reference_number);
CREATE INDEX idx_lender_submissions_expiry ON lender_submissions(expiry_date) WHERE expiry_date IS NOT NULL;
```

### Seed Data Migration
```sql
-- Big 5 Canadian Banks
INSERT INTO lenders (id, name, type, is_active, submission_email) VALUES
    (gen_random_uuid(), 'RBC Royal Bank', 'bank', true, 'uw@rbc.com'),
    (gen_random_uuid(), 'TD Canada Trust', 'bank', true, 'mortgage.ops@td.com'),
    (gen_random_uuid(), 'Scotiabank', 'bank', true, 'underwriting@scotiabank.com'),
    (gen_random_uuid(), 'BMO Bank of Montreal', 'bank', true, 'mortgage.underwriting@bmo.com'),
    (gen_random_uuid(), 'CIBC', 'bank', true, 'mortgage.uw@cibc.com');

-- Sample 5-year fixed products (simplified)
INSERT INTO lender_products (lender_id, product_name, mortgage_type, term_years, rate, rate_type, max_ltv_insured, max_ltv_conventional, max_amortization_insured, max_amortization_conventional, min_credit_score, max_gds, max_tds, allows_self_employed, allows_rental_income, allows_gifted_down_payment, effective_date) VALUES
    ((SELECT id FROM lenders WHERE name = 'RBC Royal Bank'), 'RBC Special Rate', 'fixed', 5, 5.250, 'discounted', 95.00, 80.00, 25, 30, 680, 39.00, 44.00, true, true, true, '2024-01-01');
```

### Data Migration Needs
- **Rate History Table:** Create `lender_product_rates_history` to track rate changes for audit (FINTRAC 5-year retention)
- **FINTRAC Audit Log:** Migrate existing >$10k transactions to new structured format

---

## 5. Security & Compliance

### OSFI B-20 Requirements
- **Stress Test Enforcement:** All rate displays and calculations must use `qualifying_rate = max(contract_rate + 2%, 5.25%)`
- **GDS/TDS Limits:** Hard caps enforced at 39% and 44% respectively; submissions exceeding limits auto-rejected
- **Audit Trail:** Every GDS/TDS calculation logged with:
  ```json
  {
    "correlation_id": "uuid",
    "application_id": "uuid",
    "gds": "decimal",
    "tds": "decimal",
    "stress_test_rate": "decimal",
    "calculation_breakdown": {
      "monthly_payment": "decimal",
      "property_tax": "decimal",
      "heating": "decimal",
      "condo_fees": "decimal",
      "other_debt": "decimal",
      "gross_income": "decimal"
    },
    "timestamp": "datetime"
  }
  ```

### FINTRAC Compliance
- **Transaction Logging:** All submissions with `loan_amount >= 10000` must log to `fintrac_transactions` table:
  ```sql
  INSERT INTO fintrac_transactions (
    transaction_id, transaction_type, amount, currency, 
    customer_id, date_submitted, status, created_at
  ) VALUES (
    submission_id, 'mortgage_application', approved_amount, 'CAD',
    application.borrower_id, submitted_at, 'submitted', NOW()
  );
  ```
- **Immutable Records:** `lender_submissions` table has no DELETE or UPDATE allowed without audit log entry
- **5-Year Retention:** All submission records retained; automated purge after 5 years to secure archive

### PIPEDA Data Handling
- **Encryption at Rest:** SIN, DOB fields from `applications` table encrypted using `common.security.encrypt_pii()` before inclusion in submission package
- **Data Minimization:** Submission package only includes:
  - Redacted SIN (last 4 digits)
  - Age range (e.g., "35-44") not exact DOB
  - No banking details unless required for verification (then encrypted)
- **Log Sanitization:** All logs strip PII; use `correlation_id` for tracing
- **Lookup Hashes:** SIN lookups use SHA256 hash, never plaintext

### Authentication & Authorization
| Endpoint | Auth Required | Scope | Ownership Check |
|----------|---------------|-------|-----------------|
| `GET /lenders` | JWT | `lender:read` | None |
| `GET /lenders/{id}/products` | JWT | `lender:read` | None |
| `POST /lenders/match` | JWT | `lender:match` | User must own application |
| `GET /applications/{id}/lender-matches` | JWT | `lender:read` | User must own application |
| `POST /applications/{id}/submissions` | JWT | `submission:create` | User must own application |
| `GET /applications/{id}/submissions` | JWT | `submission:read` | User must own application |
| `PUT /applications/{id}/submissions/{sub_id}` | JWT | `submission:update` | User must own application |

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `LenderNotFoundError` | 404 | `LENDER_001` | "Lender {id} not found" | GET /lenders/999 |
| `LenderProductNotFoundError` | 404 | `LENDER_002` | "Product {id} not found" | GET /lenders/{id}/products/999 |
| `LenderSubmissionNotFoundError` | 404 | `LENDER_003` | "Submission {id} not found" | PUT /submissions/999 |
| `LenderValidationError` | 422 | `LENDER_004` | "{field}: {reason}" | Missing required UW data |
| `LenderBusinessRuleError` | 409 | `LENDER_005` | "{rule} violated: {detail}" | Duplicate active submission |
| `ApplicationNotFoundError` | 404 | `LENDER_006` | "Application {id} not found" | POST /lenders/match with bad app ID |
| `LenderPermissionDeniedError` | 403 | `LENDER_007` | "Access denied to {resource}" | User accessing another's application |
| `LenderRateExpiredError` | 409 | `LENDER_008` | "Product rate expired on {date}" | Submitting after expiry_date |

**Error Response Format (Consistent across all endpoints):**
```json
{
  "detail": "Lender 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "LENDER_001",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

---

## Missing Details Resolution

### Rate Update Frequency & Mechanism
- **Design Decision:** Implement `RateFeedService` that polls lender rate APIs daily at 06:00 UTC
- **Mechanism:** Use Celery beat task with exponential backoff; failed updates retry 3x before alerting
- **Storage:** New table `lender_product_rate_history` tracks all changes for audit
- **Notification:** Webhook to `#lender-rates` Slack channel on significant rate changes (>0.25%)

### Lender Submission Format Standardization
- **Design Decision:** Adopt MISMO 3.4 XML standard for lender submissions
- **Implementation:** `MISMOFormatter` service converts internal JSON to MISMO XML
- **Per-Lender Overrides:** `lenders.submission_format` column stores custom XSLT templates
- **Validation:** XML schema validation before submission; log validation errors

### Rate Lock Mechanism & Duration
- **Design Decision:** Rate lock requested via `POST /applications/{id}/rate-locks`
- **Duration:** 90-120 days (configurable per lender in `lender_products.rate_lock_days`)
- **Storage:** New table `rate_locks` with columns: `id`, `submission_id`, `locked_rate`, `expires_at`, `is_active`
- **CMHC Compliance:** Rate lock expiry must be ≤ insurance approval validity (typically 90 days)

### Automated Rate Comparison Reporting Strategy
- **Design Decision:** Weekly automated report generated by `RateComparisonReporter` service
- **Format:** PDF + CSV sent to broker admin email
- **Contents:** 
  - Top 5 lowest rates per mortgage type
  - Rate trends over 30/60/90 days
  - Lender market share based on submissions
- **Retention:** Stored in document storage for 2 years (regulatory best practice)

---

## Testing Strategy

### Unit Tests (`tests/unit/test_lender.py`)
- Test LenderMatcher with various LTV/GDS/TDS scenarios
- Test stress test calculation accuracy
- Test state machine transitions
- Test PII redaction in submission packages

### Integration Tests (`tests/integration/test_lender_integration.py`)
- End-to-end lender matching workflow
- Submission creation and status update
- FINTRAC audit log verification
- Rate lock expiration handling
- Concurrent submission conflict resolution

### Test Data
- Pre-seeded lenders and products in `conftest.py`
- Mock applications with known UW outcomes
- Faker-generated SINs encrypted for PIPEDA testing

---

## Deployment Checklist

- [ ] Run `uv run alembic revision --autogenerate -m "add lender tables"`
- [ ] Execute seed migration for Big 5 banks
- [ ] Configure `RATE_LOCK_DAYS_DEFAULT` in `common/config.py`
- [ ] Set up Celery beat task for rate feed updates
- [ ] Deploy MISMO XSLT templates to storage
- [ ] Create FINTRAC audit log table retention policy (5 years)
- [ ] Add `LENDER_001` through `LENDER_008` to error code registry
- [ ] Update API gateway to enforce `lender:*` scopes
- [ ] Run `uv run pip-audit` and remediate findings
- [ ] Update `.env.example` with `LENDER_RATE_FEED_API_KEY`