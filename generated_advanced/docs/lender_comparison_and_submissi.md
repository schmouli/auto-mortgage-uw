# Lender Comparison & Submission
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Lender Comparison & Submission Module Design

**Module Path:** `modules/lender_comparison/`  
**Feature Slug:** `lender-comparison-submission`  
**Design Document:** `docs/design/lender-comparison-submission.md`

---

## 1. Endpoints

### `GET /api/v1/lenders`
List all active lenders with optional filtering.

**Query Parameters:**
- `lender_type` (optional, string): Filter by lender type (`bank`, `credit_union`, `monoline`, `private`, `mfc`)
- `is_active` (optional, boolean): Default `true`

**Response Schema (200):**
```python
{
  "lenders": List[{
    "id": UUID,
    "name": str,
    "lender_type": str,
    "is_active": bool,
    "logo_url": Optional[str],
    "submission_email": Optional[str],
    "notes": Optional[str]
  }]
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or missing JWT token
- `403 Forbidden` - User lacks `broker` or `underwriter` role

**Authentication:** Authenticated (JWT + role: broker|underwriter|admin)

---

### `GET /api/v1/lenders/{id}/products`
Retrieve all active products for a specific lender.

**Path Parameters:**
- `id` (UUID): Lender ID

**Query Parameters:**
- `mortgage_type` (optional, string): Filter by `fixed`, `variable`, `heloc`
- `is_active` (optional, boolean): Default `true`

**Response Schema (200):**
```python
{
  "lender_id": UUID,
  "products": List[{
    "id": UUID,
    "product_name": str,
    "mortgage_type": str,
    "term_years": int,
    "rate": Decimal,
    "rate_type": str,
    "max_ltv_insured": Decimal,
    "max_ltv_conventional": Decimal,
    "max_amortization_insured": int,
    "max_amortization_conventional": int,
    "min_credit_score": int,
    "max_gds": Decimal,
    "max_tds": Decimal,
    "allows_self_employed": bool,
    "allows_rental_income": bool,
    "allows_gifted_down_payment": bool,
    "prepayment_privilege_percent": Decimal,
    "portability": bool,
    "assumability": bool,
    "is_active": bool,
    "effective_date": datetime,
    "expiry_date": Optional[datetime]
  }]
}
```

**Error Responses:**
- `404 Not Found` - Lender does not exist (error_code: `LENDER_001`)
- `401 Unauthorized` - Invalid JWT
- `403 Forbidden` - Insufficient permissions

---

### `POST /api/v1/lenders/match`
Match lenders against a specific mortgage application.

**Request Body Schema:**
```python
{
  "application_id": UUID,
  "loan_amount": Decimal,           # Must match application
  "property_value": Decimal,        # Must match application
  "ltv": Decimal,                   # Calculated: loan_amount / property_value
  "gds_ratio": Decimal,             # From underwriting module
  "tds_ratio": Decimal,             # From underwriting module
  "credit_score": int,              # From applicant module
  "mortgage_type_preference": Optional[str],  # fixed|variable|heloc
  "is_insured": bool,               # CMHC insurance flag
  "self_employed": bool,
  "rental_income_requested": bool,
  "gifted_down_payment": bool
}
```

**Response Schema (200):**
```python
{
  "matches": List[{
    "rank": int,
    "lender_id": UUID,
    "lender_name": str,
    "product_id": UUID,
    "product_name": str,
    "rate": Decimal,
    "rate_type": str,
    "max_gds": Decimal,
    "max_tds": Decimal,
    "meets_gds": bool,
    "meets_tds": bool,
    "meets_ltv": bool,
    "meets_credit": bool,
    "meets_self_employed": bool,
    "meets_rental_income": bool,
    "meets_gifted_down_payment": bool,
    "flags": List[str],               # e.g., ["rate_lock_available", "high_ratio_only"]
    "conditions": List[str]           # Lender-specific conditions
  }],
  "timestamp": datetime,
  "total_matches": int
}
```

**Error Responses:**
- `422 Validation Error` - Invalid input (error_code: `LENDER_002`)
- `404 Not Found` - Application not found (error_code: `LENDER_001`)
- `409 Business Rule Violation` - Application not in eligible state (error_code: `LENDER_003`)
- `401/403` - Auth failures

**Authentication:** Authenticated (broker|underwriter)

---

### `GET /api/v1/applications/{id}/lender-matches`
Retrieve previously saved lender matches for an application.

**Path Parameters:**
- `id` (UUID): Application ID

**Response Schema (200):**
```python
{
  "application_id": UUID,
  "matches": List[{  # Same structure as POST /lenders/match response
    "rank": int,
    "lender_id": UUID,
    "lender_name": str,
    "product_id": UUID,
    "product_name": str,
    "rate": Decimal,
    "flags": List[str],
    "conditions": List[str],
    "created_at": datetime
  }]
}
```

**Error Responses:**
- `404 Not Found` - Application or matches not found (`LENDER_001`)
- `401/403` - Auth failures

---

### `POST /api/v1/applications/{id}/submissions`
Create a lender submission record.

**Path Parameters:**
- `id` (UUID): Application ID

**Request Body Schema:**
```python
{
  "lender_id": UUID,
  "product_id": UUID,
  "submitted_by": UUID,  # User ID from JWT context (auto-filled)
  "submission_package": {
    "application_summary": dict,
    "underwriting_results": dict,
    "documents": List[UUID],  # Document IDs from document module
    "fintrac_reporting": dict,  # FINTRAC data
    "broker_notes": Optional[str]
  },
  "rate_lock_requested": bool,
  "rate_lock_duration_days": Optional[int]  # Typically 30-120 days
}
```

**Response Schema (201):**
```python
{
  "submission_id": UUID,
  "application_id": UUID,
  "lender_id": UUID,
  "product_id": UUID,
  "status": str,  # "pending"
  "submitted_at": datetime,
  "lender_reference_number": Optional[str],
  "approved_rate": Optional[Decimal],
  "approved_amount": Optional[Decimal],
  "expiry_date": Optional[datetime],
  "notes": Optional[str],
  "created_at": datetime,
  "updated_at": datetime
}
```

**Error Responses:**
- `422 Validation Error` - Invalid product/lender combination (`LENDER_002`)
- `409 Conflict` - Duplicate submission to same lender (`LENDER_004`)
- `404 Not Found` - Application, lender, or product not found (`LENDER_001`)
- `403 Forbidden` - User not authorized for this application

**Authentication:** Authenticated (broker|underwriter)

---

### `GET /api/v1/applications/{id}/submissions`
List all submissions for an application.

**Path Parameters:**
- `id` (UUID): Application ID

**Query Parameters:**
- `status` (optional, string): Filter by status
- `lender_id` (optional, UUID): Filter by lender

**Response Schema (200):**
```python
{
  "application_id": UUID,
  "submissions": List[{
    "id": UUID,
    "lender_id": UUID,
    "lender_name": str,
    "product_name": str,
    "status": str,
    "submitted_at": datetime,
    "lender_reference_number": Optional[str],
    "approved_rate": Optional[Decimal],
    "approved_amount": Optional[Decimal],
    "expiry_date": Optional[datetime],
    "notes": Optional[str],
    "created_at": datetime,
    "updated_at": datetime
  }]
}
```

---

### `PUT /api/v1/applications/{id}/submissions/{sub_id}`
Update submission status (lender response).

**Path Parameters:**
- `id` (UUID): Application ID
- `sub_id` (UUID): Submission ID

**Request Body Schema:**
```python
{
  "status": str,  # "approved", "declined", "countered"
  "lender_reference_number": Optional[str],
  "lender_conditions": Optional[List[str]],
  "approved_rate": Optional[Decimal],
  "approved_amount": Optional[Decimal],
  "expiry_date": Optional[datetime],
  "notes": Optional[str]
}
```

**Response Schema (200):**
```python
{
  "id": UUID,
  "status": str,
  "updated_at": datetime,
  "lender_reference_number": Optional[str],
  "approved_rate": Optional[Decimal],
  "approved_amount": Optional[Decimal],
  "expiry_date": Optional[datetime]
}
```

**Error Responses:**
- `404 Not Found` - Submission not found (`LENDER_001`)
- `422 Validation Error` - Invalid status transition (`LENDER_002`)
- `409 Business Rule Error` - Rate lock expired (`LENDER_003`)

**Authentication:** Authenticated (underwriter|admin) - lender portal integration

---

## 2. Models & Database

### `lenders` Table
```sql
CREATE TABLE lenders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    lender_type VARCHAR(50) NOT NULL CHECK (lender_type IN ('bank', 'credit_union', 'monoline', 'private', 'mfc')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    logo_url VARCHAR(500),
    submission_email VARCHAR(255),
    notes TEXT,
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT idx_lenders_type_active UNIQUE (lender_type, id) WHERE is_active = true
);

CREATE INDEX idx_lenders_active ON lenders(is_active) WHERE is_active = true;
CREATE INDEX idx_lenders_name ON lenders(name);
```

### `lender_products` Table
```sql
CREATE TABLE lender_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lender_id UUID NOT NULL REFERENCES lenders(id) ON DELETE CASCADE,
    
    -- Product definition
    product_name VARCHAR(255) NOT NULL,
    mortgage_type VARCHAR(50) NOT NULL CHECK (mortgage_type IN ('fixed', 'variable', 'heloc')),
    term_years INTEGER NOT NULL CHECK (term_years > 0),
    rate DECIMAL(6,4) NOT NULL,  -- e.g., 5.2500%
    rate_type VARCHAR(50) NOT NULL CHECK (rate_type IN ('posted', 'discounted', 'prime_plus')),
    
    -- Underwriting thresholds
    max_ltv_insured DECIMAL(5,2) NOT NULL CHECK (max_ltv_insured <= 100.00),
    max_ltv_conventional DECIMAL(5,2) NOT NULL CHECK (max_ltv_conventional <= 80.00),
    max_amortization_insured INTEGER NOT NULL CHECK (max_amortization_insured <= 25),
    max_amortization_conventional INTEGER NOT NULL CHECK (max_amortization_conventional <= 30),
    min_credit_score INTEGER NOT NULL CHECK (min_credit_score >= 300),
    max_gds DECIMAL(5,2) NOT NULL CHECK (max_gds <= 100.00),
    max_tds DECIMAL(5,2) NOT NULL CHECK (max_tds <= 100.00),
    
    -- Policy flags
    allows_self_employed BOOLEAN NOT NULL DEFAULT false,
    allows_rental_income BOOLEAN NOT NULL DEFAULT false,
    allows_gifted_down_payment BOOLEAN NOT NULL DEFAULT false,
    prepayment_privilege_percent DECIMAL(5,2),
    portability BOOLEAN NOT NULL DEFAULT false,
    assumability BOOLEAN NOT NULL DEFAULT false,
    
    -- Lifecycle
    is_active BOOLEAN NOT NULL DEFAULT true,
    effective_date TIMESTAMPTZ NOT NULL,
    expiry_date TIMESTAMPTZ,
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT idx_lender_products_lender_active UNIQUE (lender_id, id) WHERE is_active = true
);

CREATE INDEX idx_lender_products_rate ON lender_products(rate, is_active) WHERE is_active = true;
CREATE INDEX idx_lender_products_lender ON lender_products(lender_id);
CREATE INDEX idx_lender_products_mortgage_type ON lender_products(mortgage_type) WHERE is_active = true;
CREATE INDEX idx_lender_products_effective_date ON lender_products(effective_date, expiry_date);
```

### `lender_submissions` Table
```sql
CREATE TABLE lender_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    lender_id UUID NOT NULL REFERENCES lenders(id) ON DELETE RESTRICT,
    product_id UUID NOT NULL REFERENCES lender_products(id) ON DELETE RESTRICT,
    submitted_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    
    -- Submission tracking
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL CHECK (status IN ('pending', 'approved', 'declined', 'countered')),
    lender_reference_number VARCHAR(100),
    lender_conditions JSONB,  -- Array of condition strings
    approved_rate DECIMAL(6,4),
    approved_amount DECIMAL(12,2),
    expiry_date TIMESTAMPTZ,
    notes TEXT,
    
    -- Audit fields (FINTRAC immutable trail)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_lender_application UNIQUE (application_id, lender_id, product_id, submitted_at)
);

CREATE INDEX idx_submissions_application ON lender_submissions(application_id);
CREATE INDEX idx_submissions_lender ON lender_submissions(lender_id);
CREATE INDEX idx_submissions_status ON lender_submissions(status);
CREATE INDEX idx_submissions_submitted_at ON lender_submissions(submitted_at);
CREATE INDEX idx_submissions_expiry ON lender_submissions(expiry_date) WHERE status = 'approved';
```

---

## 3. Business Logic

### LenderMatcher Service Algorithm

**Input:** Application financial profile, mortgage preferences  
**Output:** Ranked list of eligible lender products

**Matching Steps:**
1. **LTV Validation (CMHC Compliance)**
   ```python
   if is_insured:
       eligible = product.max_ltv_insured >= application.ltv
   else:
       eligible = product.max_ltv_conventional >= application.ltv
   ```
   - LTV calculated as: `loan_amount / property_value` (Decimal, 5+ precision)
   - If LTV > 80%, insurance_required = True per CMHC rules

2. **OSFI B-20 Stress Test Enforcement**
   ```python
   qualifying_rate = max(contract_rate + 2%, Decimal('5.25'))
   # Stress test GDS/TDS must be recalculated using qualifying_rate
   # Reject if stressed GDS > 39% or TDS > 44%
   ```

3. **Credit Score Filter**
   ```python
   eligible = application.credit_score >= product.min_credit_score
   ```

4. **Policy Flag Filters**
   ```python
   if application.self_employed and not product.allows_self_employed: reject
   if application.rental_income_requested and not product.allows_rental_income: reject
   if application.gifted_down_payment and not product.allows_gifted_down_payment: reject
   ```

5. **GDS/TDS Threshold Validation**
   ```python
   meets_gds = application.gds_ratio <= product.max_gds
   meets_tds = application.tds_ratio <= product.max_tds
   ```

6. **Ranking Logic**
   - Primary sort: `rate ASC` (lowest rate first)
   - Secondary sort: `max_gds DESC, max_tds DESC` (most flexible)
   - Tertiary sort: `allows_self_employed DESC, allows_rental_income DESC`

7. **Flag Generation**
   - `rate_lock_available`: If lender supports rate holds
   - `high_ratio_only`: If product only accepts LTV > 80%
   - `conventional_only`: If product only accepts LTV ≤ 80%
   - `stress_test_passed`: OSFI B-20 compliance indicator

### SubmissionPackageGenerator Service

**Compiles immutable FINTRAC-compliant package:**

1. **Application Summary**
   - Application ID, creation date, broker ID
   - Property details (address, value, type)
   - Loan details (amount, purpose, LTV)
   - **NO PII** - SIN/DOB excluded (PIPEDA)

2. **Underwriting Results**
   - GDS/TDS ratios (with stress test values)
   - Credit score
   - Income verification status
   - Property appraisal value
   - CMHC insurance requirement flag

3. **Document Manifest**
   - List of document IDs from document module
   - Document types: income_proof, identity_verification, property_docs
   - FINTRAC reporting flag if transaction > CAD $10,000

4. **FINTRAC Reporting Data**
   ```python
   {
     "transaction_amount": Decimal,
     "exceeds_10000": bool,
     "third_party_involvement": bool,
     "funding_method": str,  # wire|certified_cheque|etc
     "source_of_funds_verified": bool
   }
   ```

5. **Broker Notes**
   - Free text field
   - Automatically scanned for PII patterns (blocked per PIPEDA)

---

## 4. Migrations

### Alembic Revision: `create_lender_comparison_tables`

**New Tables:**
- `lenders`
- `lender_products`
- `lender_submissions`

**Indexes:**
- Composite index on `lender_products(lender_id, is_active, rate)`
- Partial index on `lender_submissions(status = 'pending')`
- GIN index on `lender_submissions.lender_conditions` (JSONB)

**Data Migration:**
- Seed `lenders` table with Big 5 Canadian banks:
  - RBC Royal Bank
  - TD Canada Trust
  - Scotiabank
  - BMO Bank of Montreal
  - CIBC
- Seed sample `lender_products` for each bank (3-5 products each)
- Seed monoline lenders: First National, MCAP, RMG Mortgages

**Constraints:**
- Add CHECK constraint: `lender_products.max_ltv_insured > 80.00`
- Add CHECK constraint: `lender_products.max_ltv_conventional <= 80.00`

---

## 5. Security & Compliance

### OSFI B-20 Requirements
- **Stress Test:** All matched products must include stress test calculation in `meets_gds`/`meets_tds` flags
- **Hard Limits:** Filter out products where applicant's GDS > 39% or TDS > 44% after stress test
- **Audit Logging:** Log calculation breakdown with correlation_id:
  ```json
  {
    "event": "lender_match_calculated",
    "correlation_id": "...",
    "application_id": "...",
    "qualifying_rate": "5.25",
    "stressed_gds": "38.5",
    "stressed_tds": "42.1",
    "osfi_compliant": true
  }
  ```

### FINTRAC Compliance
- **Immutable Audit Trail:** `lender_submissions` records are INSERT-only; `updated_at` tracks status changes but no DELETE
- **Transaction Threshold:** If `loan_amount >= 10000`, set `exceeds_10000 = true` in submission package
- **5-Year Retention:** All submission records retained per `created_at` timestamp; soft delete only
- **Identity Verification:** Document manifest must include `identity_verification` type documents

### CMHC Insurance Logic
- **LTV Calculation:** Use `Decimal` with 5+ digit precision: `loan_amount / property_value`
- **Premium Tier Lookup:**
  - 80.01-85% → `premium_rate = 2.80%`
  - 85.01-90% → `premium_rate = 3.10%`
  - 90.01-95% → `premium_rate = 4.00%`
- **Insurance Flag:** If LTV > 80%, `insurance_required = True` must be present in submission package

### PIPEDA Data Handling
- **No PII in Logs:** `SubmissionPackageGenerator` must exclude SIN, DOB, full income values
- **Encrypted Fields:** Application-level encrypted fields (SIN, DOB) never referenced directly; use hashed SIN for lookups only
- **Data Minimization:** Submission package only includes fields necessary for underwriting decision
- **Broker Notes Scanning:** Implement regex pattern matching to detect and redact potential SIN/DOB in notes

### Authentication & Authorization
- **All endpoints:** JWT required
- **Role-based access:**
  - `broker`: Can POST matches, create submissions, view own submissions
  - `underwriter`: Can update submission status, view all submissions
  - `admin`: Full CRUD on lenders and products
- **mTLS:** Lender-facing status update endpoints (if external API) require mutual TLS

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `LenderNotFoundError` | 404 | `LENDER_001` | "Lender {id} not found" | Invalid lender_id in path/body |
| `ProductNotFoundError` | 404 | `LENDER_002` | "Product {id} not found" | Invalid product_id |
| `ApplicationNotFoundError` | 404 | `LENDER_003` | "Application {id} not found" | Invalid application_id |
| `LenderValidationError` | 422 | `LENDER_004` | "{field}: {reason}" | Pydantic validation failure |
| `OSFIComplianceError` | 409 | `LENDER_005` | "OSFI B-20 violated: GDS/TDS exceeds limits" | Stressed ratios > 39%/44% |
| `DuplicateSubmissionError` | 409 | `LENDER_006` | "Duplicate submission to {lender}" | Unique constraint violation |
| `RateLockExpiredError` | 409 | `LENDER_007` | "Rate lock expired on {date}" | expiry_date < NOW() |
| `ProductIneligibleError` | 422 | `LENDER_008` | "Product ineligible: {reason}" | LTV, credit, or policy mismatch |
| `UnauthorizedAccessError` | 403 | `LENDER_009` | "Access denied to submission {id}" | User not owner/underwriter |
| `FINTRACReportingError` | 422 | `LENDER_010` | "FINTRAC data incomplete: {field}" | Missing required FINTRAC fields |

**Error Response Format (JSON):**
```json
{
  "detail": "Lender 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "LENDER_001",
  "correlation_id": "req-123456789",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

**Logging Requirements:**
- All errors logged with `structlog` at WARNING level
- Include `correlation_id`, `user_id`, `application_id` (if applicable)
- **NEVER** log SIN, DOB, income, or banking data in error messages

---

## Additional Considerations

### Rate Update Mechanism
- **Frequency:** Lender rates updated via nightly batch job or real-time API
- **Source:** Lender rate feeds (CSV, API, Bloomberg)
- **Versioning:** Rate changes create new `lender_products` records; old records marked `is_active = false` (FINTRAC audit trail)
- **Rate Lock:** When submission created, snapshot current rate into `lender_submissions.approved_rate` if approved

### Lender Submission Format
- **Standardization:** Implement `LenderSubmissionAdapter` pattern for each lender's unique format
- **Output Formats:** PDF package, JSON payload, XML (for legacy lenders)
- **Delivery:** Email (submission_email), SFTP, or API POST

### Rate Lock Mechanism
- **Duration:** 30-120 days based on lender policy
- **Storage:** `expiry_date` in `lender_submissions`
- **Extension:** Requires new submission record (FINTRAC audit)
- **Automatic Expiry:** Background job marks `status = 'declined'` if `expiry_date` passed and status still `pending`

### Automated Rate Comparison Reporting
- **Report Generation:** Weekly job comparing rates across lenders for standardized profiles
- **Storage:** Save to `rate_comparison_reports` table (separate module)
- **Access:** Available to admin users only
- **PII:** Reports contain aggregate data only, no applicant identifiers

---

**Design Complete:** This plan provides a comprehensive, regulatory-compliant foundation for lender comparison and submission functionality.