# Design: Lender Comparison & Submission
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Lender Comparison & Submission Module Design

**Document Location:** `docs/design/lender-comparison-submission.md`  
**Module Path:** `modules/lender/`  
**Feature Scope:** Lender product matching, submission package generation, and submission lifecycle management

---

## 1. Endpoints

All endpoints prefixed with `/api/v1`. Authentication required via JWT bearer token for all operations.

### 1.1 GET /lenders
List all active lenders with pagination.

**Query Parameters:**
- `limit` (optional, int, default=50, max=200)
- `offset` (optional, int, default=0)
- `type` (optional, str, enum: bank/credit_union/monoline/private/mfc)

**Response Schema (`LenderListResponse`):**
```python
{
    "total": int,
    "limit": int,
    "offset": int,
    "lenders": List[LenderSchema]
}
```

**`LenderSchema`:**
- `id`: uuid
- `name`: str
- `type`: str (enum)
- `is_active`: bool
- `logo_url`: Optional[str]
- `submission_email`: Optional[str]
- `notes`: Optional[str]
- `created_at`: datetime

**Error Responses:**
- `401 Unauthorized` → `AUTH_001` (missing/invalid token)
- `403 Forbidden` → `AUTH_002` (insufficient broker privileges)

---

### 1.2 GET /lenders/{id}/products
Retrieve all active products for a specific lender.

**Path Parameters:**
- `id`: uuid (lender identifier)

**Query Parameters:**
- `mortgage_type` (optional, str, enum: fixed/variable/heloc)
- `is_active` (optional, bool, default=true)

**Response Schema (`LenderProductListResponse`):**
```python
{
    "lender_id": uuid,
    "lender_name": str,
    "products": List[LenderProductSchema]
}
```

**`LenderProductSchema`:**
- `id`: uuid
- `product_name`: str
- `mortgage_type`: str (enum)
- `term_years`: int
- `rate`: Decimal (5,3)
- `rate_type`: str (enum)
- `max_ltv_insured`: Decimal (5,2)
- `max_ltv_conventional`: Decimal (5,2)
- `max_amortization_insured`: int
- `max_amortization_conventional`: int
- `min_credit_score`: int
- `max_gds`: Decimal (5,2)
- `max_tds`: Decimal (5,2)
- `allows_self_employed`: bool
- `allows_rental_income`: bool
- `allows_gifted_down_payment`: bool
- `prepayment_privilege_percent`: Optional[Decimal (5,2)]
- `portability`: bool
- `assumability`: bool
- `is_active`: bool
- `effective_date`: date
- `expiry_date`: Optional[date]

**Error Responses:**
- `401 Unauthorized` → `AUTH_001`
- `403 Forbidden` → `AUTH_002`
- `404 Not Found` → `LENDER_001` (lender not found or inactive)

---

### 1.3 POST /lenders/match
Match lender products against a specific mortgage application.

**Request Schema (`LenderMatchRequest`):**
```python
{
    "application_id": uuid,  # required
    "include_inactive": Optional[bool] = false,  # admin only
    "filter_by": Optional[LenderMatchFilter]
}
```

**`LenderMatchFilter`:**
- `mortgage_type`: Optional[str] (enum)
- `min_term_years`: Optional[int]
- `max_term_years`: Optional[int]
- `allows_self_employed`: Optional[bool]
- `allows_rental_income`: Optional[bool]

**Response Schema (`LenderMatchResponse`):**
```python
{
    "application_id": uuid,
    "matches": List[MatchedProductSchema]
}
```

**`MatchedProductSchema`:**
- `lender_product`: LenderProductSchema (full product details)
- `lender`: LenderSchema (lender details)
- `match_score`: Decimal (3,2)  # 0.00-1.00 compatibility score
- "gds_projected": Decimal (5,2)  # OSFI stress test applied
    "tds_projected": Decimal (5,2)  # OSFI stress test applied
    "ltv_calculated": Decimal (5,2)
    "insurance_required": bool  # per CMHC rule (LTV > 80%)
    "insurance_premium_quote": Optional[Decimal (10,2)]  # if insurance_required
    "qualifying_rate": Decimal (5,3)  # max(contract_rate + 2%, 5.25%)
    "status": str  # "eligible" | "conditionally_eligible" | "ineligible"
    "ineligibility_reasons": List[str]  # human-readable rule violations
}
```

**Error Responses:**
- `401 Unauthorized` → `AUTH_001`
- `403 Forbidden` → `AUTH_002` (if include_inactive=true and not admin)
- `404 Not Found` → `APPLICATION_001` (application not found)
- `422 Unprocessable Entity` → `LENDER_003` (validation failure: missing required fields)

---

### 1.4 GET /applications/{id}/lender-matches
Retrieve previously saved lender matches for an application.

**Path Parameters:**
- `id`: uuid (application identifier)

**Response Schema (`SavedMatchesResponse`):**
```python
{
    "application_id": uuid,
    "matches": List[MatchedProductSchema],
    "generated_at": datetime,
    "generated_by": uuid  # user_id
}
```

**Error Responses:**
- `401 Unauthorized` → `AUTH_001`
- `403 Forbidden` → `AUTH_002`
- `404 Not Found` → `APPLICATION_001`

---

### 1.5 POST /applications/{id}/submissions
Create a new lender submission record.

**Path Parameters:**
- `id`: uuid (application identifier)

**Request Schema (`SubmissionCreateRequest`):**
```python
{
    "lender_id": uuid,
    "product_id": uuid,
    "notes": Optional[str] (max_length=2000)
}
```

**Response Schema (`SubmissionSchema`):**
```python
{
    "id": uuid,
    "application_id": uuid,
    "lender_id": uuid,
    "product_id": uuid,
    "submitted_by": uuid,
    "submitted_at": datetime,
    "status": str (enum: pending/approved/declined/countered),
    "lender_reference_number": Optional[str],
    "lender_conditions": Optional[dict],  # JSON structure
    "approved_rate": Optional[Decimal (5,3)],
    "approved_amount": Optional[Decimal (12,2)],
    "expiry_date": Optional[date],
    "notes": Optional[str],
    "created_at": datetime,
    "updated_at": datetime
}
```

**Error Responses:**
- `401 Unauthorized` → `AUTH_001`
- `403 Forbidden` → `AUTH_002`
- `404 Not Found` → `APPLICATION_001` or `LENDER_001` or `LENDER_002`
- `409 Conflict` → `SUBMISSION_002` (pending submission already exists for this lender)
- `422 Unprocessable Entity` → `LENDER_003` (validation failure)

---

### 1.6 GET /applications/{id}/submissions
List all submissions for an application.

**Path Parameters:**
- `id`: uuid (application identifier)

**Query Parameters:**
- `status` (optional, str, filter by status)
- `limit`, `offset` (pagination)

**Response Schema (`SubmissionListResponse`):**
```python
{
    "application_id": uuid,
    "total": int,
    "submissions": List[SubmissionSchema]
}
```

**Error Responses:**
- `401 Unauthorized` → `AUTH_001`
- `403 Forbidden` → `AUTH_002`
- `404 Not Found` → `APPLICATION_001`

---

### 1.7 PUT /applications/{id}/submissions/{sub_id}
Update submission status and lender response details.

**Path Parameters:**
- `id`: uuid (application identifier)
- `sub_id`: uuid (submission identifier)

**Request Schema (`SubmissionUpdateRequest`):**
```python
{
    "status": str (enum: pending/approved/declined/countered),
    "lender_reference_number": Optional[str],
    "lender_conditions": Optional[dict],
    "approved_rate": Optional[Decimal (5,3)],
    "approved_amount": Optional[Decimal (12,2)],
    "expiry_date": Optional[date],
    "notes": Optional[str]
}
```

**Response Schema:** `SubmissionSchema` (updated)

**Error Responses:**
- `401 Unauthorized` → `AUTH_001`
- `403 Forbidden` → `AUTH_002` (only submitter or admin can update)
- `404 Not Found` → `SUBMISSION_001` or `APPLICATION_001`
- `409 Conflict` → `LENDER_004` (status transition not allowed)
- `422 Unprocessable Entity` → `LENDER_003` (validation failure)

---

## 2. Models & Database

### 2.1 lenders Table
```sql
CREATE TABLE lenders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('bank', 'credit_union', 'monoline', 'private', 'mfc')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    logo_url VARCHAR(500),
    submission_email VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_lenders_type ON lenders(type);
CREATE INDEX idx_lenders_is_active ON lenders(is_active) WHERE is_active = true;
```

**Relationships:**
- One-to-many with `lender_products` (cascade delete restricted)
- One-to-many with `lender_submissions` (cascade delete restricted)

---

### 2.2 lender_products Table
```sql
CREATE TABLE lender_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lender_id UUID NOT NULL REFERENCES lenders(id) ON DELETE RESTRICT,
    product_name VARCHAR(255) NOT NULL,
    mortgage_type VARCHAR(50) NOT NULL CHECK (mortgage_type IN ('fixed', 'variable', 'heloc')),
    term_years INTEGER NOT NULL CHECK (term_years > 0),
    rate DECIMAL(5,3) NOT NULL CHECK (rate >= 0),
    rate_type VARCHAR(50) NOT NULL CHECK (rate_type IN ('posted', 'discounted', 'prime_plus')),
    max_ltv_insured DECIMAL(5,2) NOT NULL CHECK (max_ltv_insured > 0),
    max_ltv_conventional DECIMAL(5,2) NOT NULL CHECK (max_ltv_conventional > 0),
    max_amortization_insured INTEGER NOT NULL CHECK (max_amortization_insured > 0),
    max_amortization_conventional INTEGER NOT NULL CHECK (max_amortization_conventional > 0),
    min_credit_score INTEGER NOT NULL CHECK (min_credit_score >= 300),
    max_gds DECIMAL(5,2) NOT NULL CHECK (max_gds > 0),
    max_tds DECIMAL(5,2) NOT NULL CHECK (max_tds > 0),
    allows_self_employed BOOLEAN NOT NULL DEFAULT false,
    allows_rental_income BOOLEAN NOT NULL DEFAULT false,
    allows_gifted_down_payment BOOLEAN NOT NULL DEFAULT false,
    prepayment_privilege_percent DECIMAL(5,2),
    portability BOOLEAN NOT NULL DEFAULT false,
    assumability BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    effective_date DATE NOT NULL,
    expiry_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_lender_products_lender_id ON lender_products(lender_id);
CREATE INDEX idx_lender_products_mortgage_type ON lender_products(mortgage_type);
CREATE INDEX idx_lender_products_is_active ON lender_products(is_active) WHERE is_active = true;
CREATE INDEX idx_lender_products_rate ON lender_products(rate);
CREATE INDEX idx_lender_products_effective_expiry ON lender_products(effective_date, expiry_date);
```

**Relationships:**
- Many-to-one with `lenders`
- One-to-many with `lender_submissions`

---

### 2.3 lender_submissions Table
```sql
CREATE TABLE lender_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE RESTRICT,
    lender_id UUID NOT NULL REFERENCES lenders(id) ON DELETE RESTRICT,
    product_id UUID NOT NULL REFERENCES lender_products(id) ON DELETE RESTRICT,
    submitted_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'declined', 'countered')),
    lender_reference_number VARCHAR(100),
    lender_conditions JSONB,
    approved_rate DECIMAL(5,3),
    approved_amount DECIMAL(12,2),
    expiry_date DATE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_lender_submissions_application_id ON lender_submissions(application_id);
CREATE INDEX idx_lender_submissions_lender_id ON lender_submissions(lender_id);
CREATE INDEX idx_lender_submissions_status ON lender_submissions(status);
CREATE INDEX idx_lender_submissions_submitted_by ON lender_submissions(submitted_by);
CREATE UNIQUE INDEX idx_lender_submissions_unique_pending ON lender_submissions(application_id, lender_id) WHERE status = 'pending';
```

**Relationships:**
- Many-to-one with `applications`, `lenders`, `lender_products`, `users`

**Audit & Compliance Notes:**
- `created_at`/`updated_at` mandatory per FINTRAC 5-year retention
- No deletion allowed; status updates only
- `lender_conditions` JSONB stores immutable lender feedback
- `submitted_by` ensures non-repudiation

---

## 3. Business Logic

### 3.1 LenderMatcher Service
**Algorithm Specification:**

```python
def match_lenders(application_id: UUID, filters: Optional[LenderMatchFilter]) -> List[MatchedProduct]:
    """
    1. Fetch application data (property_value, loan_amount, gross_income, 
       monthly_debts, credit_score, employment_type, etc.)
    2. Calculate LTV = loan_amount / property_value  # Decimal division
    3. Determine insurance_required = LTV > 80.00  # CMHC rule
    4. Calculate OSFI stress test rate:
       qualifying_rate = max(product_rate + 2.00%, 5.25%)
    5. Project monthly payment PITH using qualifying_rate
    6. Calculate GDS = (PITH / gross_monthly_income) * 100
    7. Calculate TDS = ((PITH + monthly_debts) / gross_monthly_income) * 100
    8. Query lender_products WHERE:
       - is_active = true
       - effective_date <= CURRENT_DATE
       - (expiry_date IS NULL OR expiry_date >= CURRENT_DATE)
       - LTV <= max_ltv_insured OR LTV <= max_ltv_conventional
       - credit_score >= min_credit_score
       - GDS <= max_gds
       - TDS <= max_tds
       - (allows_self_employed = true OR applicant_is_self_employed = false)
       - (allows_rental_income = true OR applicant_has_rental_income = false)
       - (allows_gifted_down_payment = true OR down_payment_is_gifted = false)
    9. Sort results by rate ASC
    10. For each match, compute:
        - match_score: compatibility 0-1 based on rule adherence
        - status: "eligible" if all rules pass, "conditionally_eligible" if minor exceedances, "ineligible" if hard limits exceeded
        - ineligibility_reasons: list of violated rules
    11. Log calculation breakdown with correlation_id for OSFI audit
    12. Return ranked list
    """
```

**OSFI B-20 Compliance:** All ratio calculations must log `qualifying_rate`, `gds_projected`, `tds_projected`, `ltv_calculated` with `correlation_id` for regulatory audit.

---

### 3.2 SubmissionPackageGenerator Service
**Package Compilation:**

```python
def generate_package(application_id: UUID, lender_id: UUID, product_id: UUID) -> SubmissionPackage:
    """
    1. Fetch application summary (redacted: no SIN/DOB/banking)
    2. Fetch underwriting results (GDS/TDS/LTV with stress test values)
    3. Fetch document manifest (document_ids, types, upload_dates)
    4. Check FINTRAC threshold: if loan_amount > 10,000 CAD, add flag
    5. Append broker notes (data minimization: only underwriting-relevant notes)
    6. Compile JSON structure:
       {
         "application_summary": { ... },
         "underwriting_results": {
           "gds": Decimal,
           "tds": Decimal,
           "ltv": Decimal,
           "qualifying_rate": Decimal,
           "credit_score": int,
           "insurance_required": bool
         },
         "documents": List[DocumentRef],
         "fintrac_flag": bool,
         "broker_notes": Optional[str]
       }
    7. Return package (never includes encrypted PII)
    """
```

**FINTRAC Compliance:** Package generation logs identity verification event with `created_by` and `correlation_id`.

---

### 3.3 State Machine & Validation Rules

**Submission Status Transitions:**
```
pending → approved (valid)
pending → declined (valid)
pending → countered (valid)
countered → approved (valid)
countered → declined (valid)
pending → pending (no-op)
any → deleted (FORBIDDEN - never delete)
```

**Hard Validation Rules:**
- `LENDER_004`: Application must be in `underwriting` or `approved` state to submit
- `LENDER_004`: Cannot create duplicate pending submission for same `(application_id, lender_id)`
- `LENDER_004`: Lender must be `is_active=true`
- `LENDER_004`: Product must be `is_active=true` and `expiry_date` must be null or future
- `LENDER_003`: `approved_rate` must be > 0 if status is `approved`
- `LENDER_003`: `approved_amount` must be ≤ loan_amount requested

---

## 4. Migrations

**Alembic Revision ID:** `20240101000001_create_lender_module`  
**Dependencies:** Base migration (applications table must exist)

### Operations
```python
def upgrade():
    # Create lenders table
    op.create_table('lenders', ...)
    
    # Create lender_products table
    op.create_table('lender_products', ...)
    op.create_foreign_key('fk_lender_products_lender_id', 'lender_products', 'lenders', ['lender_id'], ['id'])
    
    # Create lender_submissions table
    op.create_table('lender_submissions', ...)
    op.create_foreign_key('fk_lender_submissions_application_id', 'lender_submissions', 'applications', ['application_id'], ['id'])
    op.create_foreign_key('fk_lender_submissions_lender_id', 'lender_submissions', 'lenders', ['lender_id'], ['id'])
    op.create_foreign_key('fk_lender_submissions_product_id', 'lender_submissions', 'lender_products', ['product_id'], ['id'])
    op.create_foreign_key('fk_lender_submissions_submitted_by', 'lender_submissions', 'users', ['submitted_by'], ['id'])
    
    # Create all indexes
    op.create_index('idx_lenders_type', 'lenders', ['type'])
    op.create_index('idx_lenders_is_active', 'lenders', ['is_active'], postgresql_where=sa.text('is_active = true'))
    op.create_index('idx_lender_products_lender_id', 'lender_products', ['lender_id'])
    op.create_index('idx_lender_products_rate', 'lender_products', ['rate'])
    op.create_index('idx_lender_submissions_application_id', 'lender_submissions', ['application_id'])
    op.create_index('idx_lender_submissions_status', 'lender_submissions', ['status'])
    op.create_index('idx_lender_submissions_unique_pending', 'lender_submissions', ['application_id', 'lender_id'], unique=True, postgresql_where=sa.text("status = 'pending'"))

def downgrade():
    op.drop_index('idx_lender_submissions_unique_pending')
    op.drop_table('lender_submissions')
    op.drop_table('lender_products')
    op.drop_table('lenders')
```

### Seed Data (Big 5 Banks)
```sql
INSERT INTO lenders (id, name, type, submission_email) VALUES
(gen_random_uuid(), 'Royal Bank of Canada', 'bank', 'mortgage.submissions@rbc.com'),
(gen_random_uuid(), 'Toronto-Dominion Bank', 'bank', 'brokerage@td.com'),
(gen_random_uuid(), 'Scotiabank', 'bank', 'mortgage.broker@scotiabank.com'),
(gen_random_uuid(), 'Bank of Montreal', 'bank', 'mortgage.services@bmo.com'),
(gen_random_uuid(), 'Canadian Imperial Bank of Commerce', 'bank', 'mortgage.submissions@cibc.com');
```

---

## 5. Security & Compliance

### OSFI B-20 Requirements
- **Stress Test Enforcement:** `LenderMatcher` must calculate `qualifying_rate = max(product.rate + 2.00%, 5.25%)` for every product evaluated.
- **Hard Limit Validation:** Log warning if any product's `max_gds > 39.00` or `max_tds > 44.00` (regulatory ceiling).
- **Audit Logging:** Every ratio calculation logs `correlation_id`, `application_id`, `lender_id`, `product_id`, `qualifying_rate`, `gds_projected`, `tds_projected`, `ltv_calculated` in JSON format via structlog.

### FINTRAC Requirements
- **Immutable Audit Trail:** `lender_submissions` table has no DELETE endpoint; `created_at`/`updated_at` tracked.
- **Large Transaction Flag:** Submission package auto-flags if `loan_amount > 10000.00` CAD.
- **Identity Verification Log:** Broker identity (`submitted_by`) and timestamp logged for every submission.
- **5-Year Retention:** Database retention policy configured in PostgreSQL; archived records moved to `lender_submissions_history` partition after 5 years.

### CMHC Insurance Logic
- **LTV Calculation:** `ltv = loan_amount / property_value` (Decimal with 2 decimal places, no precision loss).
- **Premium Tier Lookup:** If `insurance_required` (LTV > 80.00%), calculate premium:
  - 80.01-85.00% → 2.80% of loan_amount
  - 85.01-90.00% → 3.10% of loan_amount
  - 90.01-95.00% → 4.00% of loan_amount
- **Premium Quote:** Included in `MatchedProductSchema.insurance_premium_quote`.

### PIPEDA Data Handling
- **No PII in Module Tables:** `lenders`, `lender_products`, `lender_submissions` contain no SIN/DOB/banking data.
- **Application Data Redaction:** `SubmissionPackageGenerator` strips SIN/DOB from `application_summary` using `security.encrypt_pii()` before packaging.
- **Hashed Lookups:** If SIN-based lookups needed, use SHA256 hash; never log or return plaintext.
- **Data Minimization:** Broker notes field limited to 2000 chars; only underwriting-relevant context allowed.

### Authentication & Authorization
| Endpoint | Required Role | Scope |
|----------|---------------|-------|
| `GET /lenders` | `broker`, `admin` | `lender:read` |
| `GET /lenders/{id}/products` | `broker`, `admin` | `lender:read` |
| `POST /lenders/match` | `broker`, `admin` | `lender:match` |
| `POST /applications/{id}/submissions` | `broker` | `submission:create` |
| `PUT /applications/{id}/submissions/{sub_id}` | `broker` (own submissions) or `admin` | `submission:update` |

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `LenderNotFoundError` | 404 | `LENDER_001` | "Lender {id} not found" | Request to inactive lender |
| `LenderProductNotFoundError` | 404 | `LENDER_002` | "Lender product {id} not found" | Product expired or inactive |
| `LenderValidationError` | 422 | `LENDER_003` | "{field}: {reason}" | Invalid UUID format, rate < 0 |
| `LenderBusinessRuleError` | 409 | `LENDER_004` | "{rule} violated: {detail}" | Duplicate pending submission |
| `LenderSubmissionNotFoundError` | 404 | `SUBMISSION_001` | "Submission {id} not found" | Invalid sub_id |
| `LenderSubmissionConflictError` | 409 | `SUBMISSION_002` | "Pending submission already exists for lender {lender_id}" | Double submission attempt |
| `ApplicationNotFoundError` | 404 | `APPLICATION_001` | "Application {id} not found" | Invalid application_id |
| `UnauthorizedError` | 401 | `AUTH_001` | "Authentication required" | Missing JWT token |
| `ForbiddenError` | 403 | `AUTH_002` | "Insufficient permissions" | Broker accessing admin endpoint |

**Error Response Structure (consistent across all endpoints):**
```json
{
    "detail": "Lender 123e4567-e89b-12d3-a456-426614174000 not found",
    "error_code": "LENDER_001",
    "correlation_id": "af3d7c9e-8b2a-4c1d-9e5f-8b3c2a9d7e1f",
    "timestamp": "2024-01-01T12:00:00Z"
}
```

---

## 7. Observability & Monitoring

- **Metrics:** Prometheus counters for `lender_matches_generated`, `submissions_created`, `submission_status_updates`.
- **Tracing:** OpenTelemetry spans for `LenderMatcher.match()` and `SubmissionPackageGenerator.generate()` with attributes `lender.id`, `product.id`, `application.id`.
- **Logging:** structlog JSON logs for every ratio calculation, submission creation, and status transition. `correlation_id` propagated from FastAPI middleware.

---

## 8. Future Considerations (Out of Scope)

- **Rate Update Mechanism:** Batch ETL from lender rate feeds or SFTP; scheduled Airflow job.
- **Rate Lock:** Separate `rate_locks` table with expiry tracking; requires lender API integration.
- **Submission Format Standardization:** PDF generation via `weasyprint` or lender-specific XML/JSON schemas.
- **Automated Comparison Reporting:** Weekly report generation module; uses `lender_matches` historical data.

---

**Next Steps:** Implementation tickets to be created for `models.py`, `schemas.py`, `services.py`, `routes.py`, and `exceptions.py` with corresponding unit and integration tests.