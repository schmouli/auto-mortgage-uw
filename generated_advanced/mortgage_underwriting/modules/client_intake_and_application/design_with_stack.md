# Design: Client Intake & Application
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Client Intake & Application Module Design

**Module Identifier:** `APP`  
**Feature Slug:** `client-intake-application`  
**Design Document:** `docs/design/client-intake-application.md`

---

## 1. Endpoints

### `POST /api/v1/applications`
Create a new mortgage application (starts in `draft` status).

**Authentication:** Authenticated client or broker

**Request Body Schema:**
```python
class ApplicationCreateRequest(BaseModel):
    client_id: UUID  # Must belong to authenticated user
    application_type: Literal["purchase", "refinance", "renewal"]
    property_address: dict  # {street, city, province, postal_code}
    property_type: Literal["single_family", "condo", "townhouse", "duplex", "vacant_land"]
    property_value: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    purchase_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    down_payment: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    requested_loan_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    amortization_years: int = Field(ge=5, le=30)
    term_years: int = Field(ge=1, le=10)
    mortgage_type: Literal["fixed", "variable"]
    interest_rate: Decimal = Field(ge=0, le=1, max_digits=5, decimal_places=4)  # 0.05 = 5%
```

**Response Schema (201):**
```python
class ApplicationResponse(BaseModel):
    id: UUID
    client_id: UUID
    broker_id: Optional[UUID]
    application_type: str
    status: Literal["draft", "submitted", "underwriting", "approved", "rejected", "closed"]
    property_address: dict
    property_type: str
    property_value: Decimal
    purchase_price: Decimal
    down_payment: Decimal
    requested_loan_amount: Decimal
    amortization_years: int
    term_years: int
    mortgage_type: str
    interest_rate: Decimal
    created_at: datetime
    updated_at: datetime
```

**Error Responses:**
- `400`: `APP_001` - Invalid loan parameters (e.g., LTV > 95%)
- `401`: `AUTH_001` - Missing or invalid token
- `403`: `APP_002` - Client does not own this resource
- `422`: `VALID_001` - Field validation error with details

---

### `GET /api/v1/applications`
List applications with pagination and filtering.

**Authentication:** Authenticated client or broker

**Query Parameters:**
- `status`: Optional filter
- `page`: int (default: 1)
- `page_size`: int (default: 20, max: 100)

**Response Schema (200):**
```python
class ApplicationListResponse(BaseModel):
    items: List[ApplicationSummary]
    total: int
    page: int
    page_size: int

class ApplicationSummary(BaseModel):
    id: UUID
    status: str
    property_address: dict
    property_value: Decimal
    requested_loan_amount: Decimal
    created_at: datetime
```

**Error Responses:**
- `401`: `AUTH_001` - Authentication required
- `403`: `APP_003` - Broker accessing unassigned application

---

### `GET /api/v1/applications/{id}`
Get full application details.

**Authentication:** Authenticated client or broker

**Response Schema (200):** `ApplicationResponse` (same as POST)

**Error Responses:**
- `401`: `AUTH_001`
- `403`: `APP_003` - Access denied
- `404`: `APP_004` - Application not found

---

### `PUT /api/v1/applications/{id}`
Update application (only allowed in `draft` status).

**Authentication:** Authenticated client or broker

**Request Body Schema:** `ApplicationUpdateRequest` (same fields as `ApplicationCreateRequest` but all optional)

**Response Schema (200):** `ApplicationResponse`

**Error Responses:**
- `400`: `APP_005` - Cannot modify non-draft application
- `401`: `AUTH_001`
- `403`: `APP_003`
- `404`: `APP_004`
- `409`: `APP_006` - Conflict (e.g., down payment changed affects insurance)

---

### `POST /api/v1/applications/{id}/submit`
Submit application for underwriting (triggers compliance checks).

**Authentication:** Authenticated client or broker

**Request Body:** None

**Response Schema (202):**
```python
class ApplicationSubmitResponse(BaseModel):
    id: UUID
    status: Literal["submitted"]
    submitted_at: datetime
    compliance_checks: List[str]  # ["FINTRAC_10000", "CMHC_INSURANCE", "OSFI_STRESS_TEST"]
```

**Error Responses:**
- `400`: `APP_007` - Missing required fields (e.g., client SIN)
- `400`: `APP_008` - Business rule violation (GDS/TDS > limits)
- `401`: `AUTH_001`
- `403`: `APP_003`
- `404`: `APP_004`
- `422`: `APP_009` - Co-borrower validation failed

---

### `GET /api/v1/applications/{id}/summary`
Get PDF-ready JSON for document generation.

**Authentication:** Authenticated client or broker

**Response Schema (200):**
```python
class ApplicationSummaryPDF(BaseModel):
    application: ApplicationResponse
    client: ClientSummary  # Excludes SIN/DOB
    co_borrowers: List[CoBorrowerSummary]
    calculations: LoanCalculationBreakdown
    compliance: ComplianceFlags
```

**Error Responses:**
- `401`, `403`, `404` as above

---

## 2. Models & Database

### `clients` Table
```sql
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sin_encrypted BYTEA NOT NULL,  -- AES-256-GCM encrypted
    sin_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA256 for lookups
    date_of_birth_encrypted BYTEA NOT NULL,  -- AES-256-GCM encrypted
    employment_status VARCHAR(50) NOT NULL CHECK (employment_status IN ('employed', 'self_employed', 'unemployed', 'retired')),
    employer_name VARCHAR(255),
    years_employed NUMERIC(4,2),
    annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
    other_income DECIMAL(12,2) DEFAULT 0.00,
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    marital_status VARCHAR(50) CHECK (marital_status IN ('single', 'married', 'common_law', 'divorced', 'widowed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT idx_clients_user_id UNIQUE (user_id),
    CONSTRAINT idx_clients_sin_hash UNIQUE (sin_hash)
);

CREATE INDEX idx_clients_created_at ON clients(created_at);
```

### `applications` Table
```sql
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    broker_id UUID REFERENCES users(id) ON DELETE SET NULL,
    application_type VARCHAR(50) NOT NULL CHECK (application_type IN ('purchase', 'refinance', 'renewal')),
    status VARCHAR(50) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'underwriting', 'approved', 'rejected', 'closed')),
    property_address JSONB NOT NULL,  -- {street, city, province, postal_code}
    property_type VARCHAR(50) NOT NULL CHECK (property_type IN ('single_family', 'condo', 'townhouse', 'duplex', 'vacant_land')),
    property_value DECIMAL(12,2) NOT NULL CHECK (property_value > 0),
    purchase_price DECIMAL(12,2) NOT NULL CHECK (purchase_price > 0),
    down_payment DECIMAL(12,2) NOT NULL CHECK (down_payment >= 0),
    requested_loan_amount DECIMAL(12,2) NOT NULL CHECK (requested_loan_amount > 0),
    amortization_years INTEGER NOT NULL CHECK (amortization_years BETWEEN 5 AND 30),
    term_years INTEGER NOT NULL CHECK (term_years BETWEEN 1 AND 10),
    mortgage_type VARCHAR(50) NOT NULL CHECK (mortgage_type IN ('fixed', 'variable')),
    interest_rate DECIMAL(5,4) NOT NULL CHECK (interest_rate >= 0),
    qualifying_rate DECIMAL(5,4),  -- OSFI stress test rate
    gds_ratio DECIMAL(5,2),  -- Gross Debt Service ratio
    tds_ratio DECIMAL(5,2),  -- Total Debt Service ratio
    cmhc_insurance_required BOOLEAN DEFAULT FALSE,
    cmhc_premium_amount DECIMAL(12,2) DEFAULT 0.00,
    cmhc_premium_rate DECIMAL(5,4),  -- 0.0280 = 2.80%
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    
    -- Indexes
    CONSTRAINT idx_applications_client_id_status UNIQUE (client_id, status) WHERE status = 'draft'
);

CREATE INDEX idx_applications_client_id ON applications(client_id);
CREATE INDEX idx_applications_broker_id ON applications(broker_id);
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_applications_submitted_at ON applications(submitted_at DESC);
CREATE INDEX idx_applications_loan_amount ON applications(requested_loan_amount);
```

### `co_borrowers` Table
```sql
CREATE TABLE co_borrowers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    sin_encrypted BYTEA NOT NULL,
    sin_hash VARCHAR(64) NOT NULL,
    annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
    employment_status VARCHAR(50) NOT NULL,
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    relationship_to_client VARCHAR(50) CHECK (relationship_to_client IN ('spouse', 'parent', 'child', 'sibling', 'other')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT idx_co_borrowers_app_sin UNIQUE (application_id, sin_hash)
);

CREATE INDEX idx_co_borrowers_application_id ON co_borrowers(application_id);
CREATE INDEX idx_co_borrowers_sin_hash ON co_borrowers(sin_hash);
```

---

## 3. Business Logic

### Application Status Workflow
```
draft → submitted → underwriting → [approved | rejected] → closed
```

**Transition Rules:**
- `draft` → `submitted`: Trigger compliance validation (OSFI, FINTRAC, CMHC)
- `submitted` → `underwriting`: Auto-transition after validation passes
- `underwriting` → `approved`: Underwriter decision (GDS ≤ 39%, TDS ≤ 44%)
- `underwriting` → `rejected`: Underwriter decision (fails ratios or policy)
- Any status → `closed`: Manual admin action (withdrawn, funded)

### Validation Rules
| Field | Rule | Error Code |
|-------|------|------------|
| purchase_price | > 0 | `APP_101` |
| down_payment | ≥ 5% of purchase_price (insured) or ≥ 20% (uninsured) | `APP_102` |
| LTV | ≤ 95% (max allowed) | `APP_103` |
| amortization_years | 5-25 (uninsured), 5-30 (insured) | `APP_104` |
| term_years | 1-10 | `APP_105` |
| annual_income | > 0 | `APP_106` |
| credit_score | ≥ 600 (minimum) | `APP_107` |

### CMHC Insurance Calculation
```python
ltv = requested_loan_amount / property_value
if ltv > Decimal('0.80'):
    cmhc_insurance_required = True
    if Decimal('0.8001') <= ltv <= Decimal('0.85'):
        cmhc_premium_rate = Decimal('0.0280')
    elif Decimal('0.8501') <= ltv <= Decimal('0.90'):
        cmhc_premium_rate = Decimal('0.0310')
    elif Decimal('0.9001') <= ltv <= Decimal('0.95'):
        cmhc_premium_rate = Decimal('0.0400')
    cmhc_premium_amount = requested_loan_amount * cmhc_premium_rate
```

### OSFI B-20 Stress Test
```python
qualifying_rate = max(contract_rate + Decimal('0.02'), Decimal('0.0525'))
# Use qualifying_rate for GDS/TDS calculations
# Log: {correlation_id, application_id, gds_ratio, tds_ratio, qualifying_rate}
```

### Co-Borrower Management
- Add: `POST /applications/{id}/co-borrowers` (draft status only)
- Remove: `DELETE /applications/{id}/co-borrowers/{co_borrower_id}` (draft only)
- Update: `PUT /applications/{id}/co-borrowers/{co_borrower_id}` (draft only)
- Maximum 3 co-borrowers per application

---

## 4. Migrations

### Alembic Revision: `create_client_intake_tables`

**New Tables:**
- `clients` (with indexes)
- `applications` (with indexes)
- `co_borrowers` (with indexes)

**New Columns on Existing Tables:**
- `users.role`: Add `broker` enum value if not exists

**Indexes:**
- Composite: `applications(client_id, status)` WHERE status = 'draft'
- Composite: `co_borrowers(application_id, sin_hash)`

**Data Migration:** None required

**Downgrade:** Drop tables in reverse dependency order

---

## 5. Security & Compliance

### PIPEDA Compliance
- **Encryption at Rest:** SIN and DOB encrypted using AES-256-GCM via `common/security.py:encrypt_pii()`
- **Key Management:** Use environment-specific key vault (AWS KMS, Azure Key Vault, or HashiCorp Vault)
- **Data Minimization:** API responses exclude `sin_encrypted`, `date_of_birth_encrypted`; only return masked SIN (last 4 digits) if absolutely necessary
- **Logging:** NEVER log SIN, DOB, income values; log only `sin_hash` for audit trails

### FINTRAC Compliance
- **Transaction Threshold:** If `requested_loan_amount ≥ CAD $10,000`, set `fintrac_flag = True`
- **Audit Trail:** All creates/updates logged to `audit_log` table with `created_by`, `correlation_id`
- **Retention:** 5-year retention enforced via database policy (PostgreSQL row-level security)

### OSFI B-20 Compliance
- **Stress Test:** `qualifying_rate` calculated on submission, stored for audit
- **GDS/TDS Limits:** Hard enforcement: GDS ≤ 39%, TDS ≤ 44%
- **Calculation Logging:** Log full breakdown:
  ```json
  {
    "correlation_id": "...",
    "application_id": "...",
    "gds_ratio": 0.35,
    "tds_ratio": 0.42,
    "qualifying_rate": 0.0625,
    "income_verified": true
  }
  ```

### CMHC Compliance
- **Insurance Requirement:** Auto-calculated when LTV > 80%
- **Premium Tiers:** Exact premium rates applied based on LTV bands
- **Premium Capitalization:** Premium added to loan amount if not paid upfront

### Access Control
- **Clients:** Can only `GET/POST/PUT` their own `user_id`-linked applications
- **Brokers:** Can only access applications where `broker_id` matches their `user_id`
- **Admins:** Full access via role-based policy

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `ApplicationNotFoundError` | 404 | `APP_001` | "Application {id} not found" | Invalid UUID or no access |
| `ApplicationValidationError` | 422 | `APP_002` | "{field}: {reason}" | Pydantic validation fails |
| `ApplicationBusinessRuleError` | 409 | `APP_003` | "{rule} violated: {detail}" | LTV > 95%, GDS/TDS > limits |
| `ApplicationAccessDeniedError` | 403 | `APP_004` | "Access denied to application {id}" | Client/broker mismatch |
| `ApplicationSubmissionError` | 400 | `APP_005` | "Cannot submit: {reason}" | Missing required fields, not draft status |
| `ApplicationStatusError` | 409 | `APP_006` | "Invalid status transition: {from} → {to}" | Illegal workflow change |
| `CoBorrowerLimitError` | 422 | `APP_007` | "Maximum co-borrowers exceeded (3)" | >3 co-borrowers |
| `SINEncryptionError` | 500 | `APP_008` | "SIN encryption failed" | Vault/key unavailable |
| `FINTRACThresholdError` | 400 | `APP_009` | "Transaction >$10K requires additional verification" | Missing identity docs |

### Structured Error Response Format
```json
{
  "detail": "GDS ratio violated: 0.42 > 0.39",
  "error_code": "APP_003",
  "correlation_id": "req-12345",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Implementation Notes

- **Encryption Service:** Use `common/security.py:encrypt_pii(data: str, key_id: str) -> bytes` and `decrypt_pii(encrypted: bytes, key_id: str) -> str`
- **Audit Logging:** All state changes write to `audit_log` table via SQLAlchemy event listeners
- **Async Validation:** Business rule validation runs in background task on submission
- **Correlation ID:** Injected by middleware, propagated to all logs and audit trails
- **Decimal Precision:** All financial calculations use `Decimal` with `quantize()` to 2 decimal places
- **Testing Markers:** Unit tests use `@pytest.mark.unit`, integration tests use `@pytest.mark.integration` and require PostgreSQL container