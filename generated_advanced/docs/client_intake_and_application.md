# Client Intake & Application
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

docs/design/client-intake-application.md
```markdown
# Client Intake & Application Module Design

**Feature slug:** `client-intake-application`  
**Module identifier:** `INTAKE`  
**Last updated:** 2025-07-20

---

## 1. Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST`   | `/api/v1/applications` | JWT (client or broker) | Create a new mortgage application (draft status). |
| `GET`    | `/api/v1/applications` | JWT (client or broker) | List applications visible to the caller (paginated). |
| `GET`    | `/api/v1/applications/{id}` | JWT (client or broker) | Retrieve a single application (full detail). |
| `PUT`    | `/api/v1/applications/{id}` | JWT (client or broker) | Update a draft application (partial or full). |
| `POST`   | `/api/v1/applications/{id}/submit` | JWT (client or broker) | Submit a draft application for underwriting (status → `submitted`). |
| `GET`    | `/api/v1/applications/{id}/summary` | JWT (client or broker) | Return a PDF‑ready JSON snapshot of the application. |

### 1.1 `POST /api/v1/applications`

**Request body (JSON) – `ApplicationCreateRequest`**

| Field | Type | Required | Validation / Remarks |
|-------|------|----------|----------------------|
| `client_id` | `uuid` | Yes | Must belong to the authenticated user (or broker’s client). |
| `application_type` | `enum` | Yes | `purchase`, `refinance`, `transfer`. |
| `property_address` | `string` | Yes | Max 255 chars. |
| `property_type` | `enum` | Yes | `single_family`, `condo`, `townhouse`, `multi_unit`. |
| `property_value` | `Decimal(12,2)` | Yes | > 0. |
| `purchase_price` | `Decimal(12,2)` | Yes | > 0. |
| `down_payment` | `Decimal(12,2)` | Yes | ≥ 5 % of `purchase_price`. |
| `requested_loan_amount` | `Decimal(12,2)` | Yes | `purchase_price − down_payment`. |
| `amortization_years` | `int` | Yes | 5‑30 (insured) or 5‑25 (uninsured). |
| `term_years` | `int` | Yes | 1‑10. |
| `mortgage_type` | `enum` | Yes | `fixed`, `variable`, `hybrid`. |
| `broker_id` | `uuid` | No | If omitted, system assigns the caller (broker) or leaves null (direct client). |

**Response – `ApplicationCreateResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `application_id` | `uuid` | New application identifier. |
| `status` | `string` | Initial status: `draft`. |
| `created_at` | `datetime` | ISO 8601 timestamp. |

**Error responses**

| HTTP | Error Code | Detail |
|------|------------|--------|
| `400` | `INTAKE_002` | `purchase_price: must be greater than 0` |
| `422` | `INTAKE_002` | `amortization_years: must be between 5 and 30 (insured) or 5 and 25 (uninsured)` |
| `422` | `INTAKE_002` | `down_payment: must be at least 5 % of purchase_price` |
| `401` | `AUTH_001` | `Authentication required` |
| `403` | `AUTH_002` | `Insufficient permissions` |

---

### 1.2 `GET /api/v1/applications`

**Query parameters**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `page` | `int` | No | Default 1. |
| `page_size` | `int` | No | Default 20, max 100. |
| `status` | `string` | No | Filter by status. |
| `broker_id` | `uuid` | No | Broker‑only filter (ignored for clients). |

**Response – `ApplicationListResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `items` | `list[ApplicationSummaryItem]` | Summaries of visible applications. |
| `total` | `int` | Total count for pagination. |
| `page` | `int` | Current page. |
| `page_size` | `int` | Items per page. |

**`ApplicationSummaryItem`**

| Field | Type | Description |
|-------|------|-------------|
| `application_id` | `uuid` |  |
| `client_id` | `uuid` |  |
| `status` | `string` |  |
| `property_address` | `string` |  |
| `property_value` | `Decimal` |  |
| `requested_loan_amount` | `Decimal` |  |
| `created_at` | `datetime` |  |

**Error responses**

| HTTP | Error Code | Detail |
|------|------------|--------|
| `401` | `AUTH_001` | `Authentication required` |
| `403` | `AUTH_002` | `Insufficient permissions` |

---

### 1.3 `GET /api/v1/applications/{id}`

**Response – `ApplicationDetailResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `application_id` | `uuid` |  |
| `client_id` | `uuid` |  |
| `broker_id` | `uuid` \| `null` |  |
| `status` | `string` |  |
| `application_type` | `enum` |  |
| `property_address` | `string` |  |
| `property_type` | `enum` |  |
| `property_value` | `Decimal` |  |
| `purchase_price` | `Decimal` |  |
| `down_payment` | `Decimal` |  |
| `requested_loan_amount` | `Decimal` |  |
| `amortization_years` | `int` |  |
| `term_years` | `int` |  |
| `mortgage_type` | `enum` |  |
| `co_borrowers` | `list[CoBorrowerItem]` | (see below) |
| `created_at` | `datetime` |  |
| `updated_at` | `datetime` |  |
| `submitted_at` | `datetime` \| `null` |  |

**`CoBorrowerItem`**

| Field | Type | Description |
|-------|------|-------------|
| `co_borrower_id` | `uuid` |  |
| `full_name` | `string` |  |
| `annual_income` | `Decimal` |  |
| `employment_status` | `enum` |  |
| `credit_score` | `int` |  |

**Error responses**

| HTTP | Error Code | Detail |
|------|------------|--------|
| `404` | `INTAKE_001` | `Application not found` |
| `401` | `AUTH_001` | `Authentication required` |
| `403` | `AUTH_002` | `Insufficient permissions` |

---

### 1.4 `PUT /api/v1/applications/{id}`

**Request body – `ApplicationUpdateRequest`**

Same fields as `ApplicationCreateRequest`, but all optional. Only `draft` applications may be updated; `submitted` or later statuses return `409`.

**Response – `ApplicationUpdateResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `application_id` | `uuid` |  |
| `status` | `string` | Unchanged (`draft`). |
| `updated_at` | `datetime` |  |

**Error responses**

| HTTP | Error Code | Detail |
|------|------------|--------|
| `404` | `INTAKE_001` | `Application not found` |
| `409` | `INTAKE_003` | `Only draft applications can be updated` |
| `422` | `INTAKE_002` | Same validation errors as `POST`. |
| `401` | `AUTH_001` | `Authentication required` |
| `403` | `AUTH_002` | `Insufficient permissions` |

---

### 1.5 `POST /api/v1/applications/{id}/submit`

**Request body – empty JSON object `{}`**

**Response – `ApplicationSubmitResponse`**

| Field | Type | Description |
|-------|------|-------------|
| `application_id` | `uuid` |  |
| `status` | `string` | New status: `submitted`. |
| `submitted_at` | `datetime` | Timestamp of submission. |

**Error responses**

| HTTP | Error Code | Detail |
|------|------------|--------|
| `404` | `INTAKE_001` | `Application not found` |
| `409` | `INTAKE_003` | `Application already submitted or withdrawn` |
| `422` | `INTAKE_002` | `Missing required fields: {list}` (e.g., client SIN, co‑borrower SIN if present). |
| `401` | `AUTH_001` | `Authentication required` |
| `403` | `AUTH_002` | `Insufficient permissions` |

---

### 1.6 `GET /api/v1/applications/{id}/summary`

**Response – `ApplicationSummaryPdfPayload`**

A JSON object designed to be fed directly into a PDF generation service (fields match the PDF template). Contains all non‑encrypted data from the application, client, and co‑borrowers, plus computed LTV, insurance flag, and premium estimate.

**Error responses**

| HTTP | Error Code | Detail |
|------|------------|--------|
| `404` | `INTAKE_001` | `Application not found` |
| `401` | `AUTH_001` | `Authentication required` |
| `403` | `AUTH_002` | `Insufficient permissions` |

---

## 2. Models & Database

### 2.1 Table: `clients`

| Column | Type | Constraints | Index | Encrypted |
|--------|------|-------------|-------|-----------|
| `id` | `UUID` | PK, default `gen_random_uuid()` | – | – |
| `user_id` | `UUID` | FK → `users.id`, not null | `ix_clients_user_id` | – |
| `sin_encrypted` | `bytea` | not null | – | **Yes** (AES‑256) |
| `date_of_birth` | `date` | not null | – | **Yes** (AES‑256) |
| `employment_status` | `varchar(50)` | not null | – | – |
| `employer_name` | `varchar(255)` | – | – | – |
| `years_employed` | `int` | – | – | – |
| `annual_income` | `Numeric(12,2)` | not null, > 0 | – | – |
| `other_income` | `Numeric(12,2)` | default 0 | – | – |
| `credit_score` | `int` | – | `ix_clients_credit_score` | – |
| `marital_status` | `varchar(50)` | – | – | – |
| `created_at` | `timestamptz` | not null, default `now()` | `ix_clients_created_at` | – |
| `updated_at` | `timestamptz` | not null, default `now()`, on update `now()` | – | – |

**Relationships**

- `user` → `users` (many‑to‑one)

**Indexes**

- `ix_clients_user_id` (foreign key)
- `ix_clients_credit_score` (filtering)
- `ix_clients_created_at` (time‑range queries)

---

### 2.2 Table: `applications`

| Column | Type | Constraints | Index | Encrypted |
|--------|------|-------------|-------|-----------|
| `id` | `UUID` | PK, default `gen_random_uuid()` | – | – |
| `client_id` | `UUID` | FK → `clients.id`, not null | `ix_applications_client_id` | – |
| `broker_id` | `UUID` | FK → `users.id`, nullable | `ix_applications_broker_id` | – |
| `application_type` | `varchar(50)` | not null (`purchase`, `refinance`, `transfer`) | `ix_applications_type` | – |
| `status` | `varchar(50)` | not null (`draft`, `submitted`, `underwriting`, `approved`, `rejected`, `withdrawn`) | `ix_applications_status` | – |
| `property_address` | `varchar(255)` | not null | – | – |
| `property_type` | `varchar(50)` | not null | – | – |
| `property_value` | `Numeric(12,2)` | not null, > 0 | – | – |
| `purchase_price` | `Numeric(12,2)` | not null, > 0 | – | – |
| `down_payment` | `Numeric(12,2)` | not null, ≥ 5 % of `purchase_price` | – | – |
| `requested_loan_amount` | `Numeric(12,2)` | not null, `purchase_price − down_payment` | – | – |
| `amortization_years` | `int` | not null, 5‑30 (insured) or 5‑25 (uninsured) | – | – |
| `term_years` | `int` | not null, 1‑10 | – | – |
| `mortgage_type` | `varchar(50)` | not null (`fixed`, `variable`, `hybrid`) | – | – |
| `created_at` | `timestamptz` | not null, default `now()` | `ix_applications_created_at` | – |
| `updated_at` | `timestamptz` | not null, default `now()`, on update `now()` | – | – |
| `submitted_at` | `timestamptz` | nullable | `ix_applications_submitted_at` | – |

**Relationships**

- `client` → `clients` (many‑to‑one)
- `broker` → `users` (many‑to‑one)
- `co_borrowers` → `co_borrowers` (one‑to‑many, cascade delete)

**Indexes**

- `ix_applications_client_id` (foreign key)
- `ix_applications_broker_id` (foreign key)
- `ix_applications_status` (workflow queries)
- `ix_applications_created_at` (time‑range reports)
- `ix_applications_submitted_at` (FINTRAC audit)

---

### 2.3 Table: `co_borrowers`

| Column | Type | Constraints | Index | Encrypted |
|--------|------|-------------|-------|-----------|
| `id` | `UUID` | PK, default `gen_random_uuid()` | – | – |
| `application_id` | `UUID` | FK → `applications.id`, not null, cascade delete | `ix_co_borrowers_application_id` | – |
| `full_name` | `varchar(255)` | not null | – | – |
| `sin_encrypted` | `bytea` | not null | – | **Yes** (AES‑256) |
| `annual_income` | `Numeric(12,2)` | not null, > 0 | – | – |
| `employment_status` | `varchar(50)` | not null | – | – |
| `credit_score` | `int` | – | `ix_co_borrowers_credit_score` | – |
| `created_at` | `timestamptz` | not null, default `now()` | `ix_co_borrowers_created_at` | – |
| `updated_at` | `timestamptz` | not null, default `now()`, on update `now()` | – | – |

**Relationships**

- `application` → `applications` (many‑to‑one)

**Indexes**

- `ix_co_borrowers_application_id` (foreign key)
- `ix_co_borrowers_credit_score` (underwriting filters)

---

### 2.4 Encryption strategy

- **Algorithm:** AES‑256‑GCM (authenticated encryption).
- **Key source:** `MORTGAGE_SIN_ENCRYPTION_KEY` environment variable (Base64‑encoded 32‑byte key), loaded via `common/config.py`.
- **Key rotation:** New keys are versioned; old keys kept for decryption. A `key_version` column (default `1`) will be added in a future migration to support rotation.
- **Encryption service:** `common/security.encrypt_pii(plaintext: str) -> bytes` and `decrypt_pii(ciphertext: bytes) -> str`.
- **Never logged:** `sin_encrypted` and `date_of_birth` are excluded from all structlog calls.

---

## 3. Business Logic

### 3.1 Validation rules (applied on `POST` and `PUT`)

| Field | Rule | Error Code |
|-------|------|------------|
| `purchase_price` | > 0 | `INTAKE_002` |
| `down_payment` | ≥ 5 % of `purchase_price` | `INTAKE_002` |
| `amortization_years` | 5‑30 if insured, 5‑25 if uninsured (CMHC max) | `INTAKE_002` |
| `term_years` | 1‑10 | `INTAKE_002` |
| `annual_income` (client & co‑borrower) | > 0 | `INTAKE_002` |
| `sin_encrypted` | Must be present and non‑empty after encryption | `INTAKE_002` |
| `application_type` | One of `purchase`, `refinance`, `transfer` | `INTAKE_002` |
| `mortgage_type` | One of `fixed`, `variable`, `hybrid` | `INTAKE_002` |

**Note:** All `Decimal` fields use `Numeric(12,2)` to avoid precision loss.

### 3.2 Application status state machine

| Status | Allowed transitions | Description |
|--------|---------------------|-------------|
| `draft` | → `submitted` | Initial state; editable. |
| `submitted` | → `underwriting` | Locked for editing; awaiting underwriter assignment. |
| `underwriting` | → `approved`, `rejected` | Underwriter review in progress. |
| `approved` | → `withdrawn` | Offer accepted; may be withdrawn before funding. |
| `rejected` | → `withdrawn` | Application denied; may be withdrawn. |
| `withdrawn` | – | Terminal state; no further changes. |

**Transition guards**

- Only the owner (client) or assigned broker can submit a draft.
- Once `submitted`, the application is immutable except for status updates by the underwriting module.
- The `PUT` endpoint returns `409` if the status is not `draft`.

### 3.3 Co‑borrower management

- **Add / update:** Include `co_borrowers` list in `PUT /applications/{id}` (draft only). The service will replace existing co‑borrowers (cascade delete + re‑insert).
- **Remove:** Send an empty list `[]` for `co_borrowers` to delete all.
- **Validation:** Each co‑borrower must have `sin_encrypted`, `full_name`, `annual_income` > 0, `employment_status`. Duplicate SIN within the same application is rejected (`INTAKE_003`).

### 3.4 CMHC insurance & LTV logic (computed on `submit`)

```python
ltv = requested_loan_amount / property_value  # Decimal, 4‑digit precision
if ltv > Decimal('0.80'):
    insurance_required = True
    if Decimal('0.8001') <= ltv <= Decimal('0.85'):
        premium_rate = Decimal('0.0280')
    elif Decimal('0.8501') <= ltv <= Decimal('0.90'):
        premium_rate = Decimal('0.0310')
    elif Decimal('0.9001') <= ltv <= Decimal('0.95'):
        premium_rate = Decimal('0.0400')
    else:
        raise BusinessRuleError("LTV exceeds 95 %")
    insurance_premium = requested_loan_amount * premium_rate
else:
    insurance_required = False
    insurance_premium = Decimal('0')
```

- The `insurance_required` flag and `insurance_premium` are stored in the `applications` table (added via migration) and returned in the summary payload.
- **Regulatory note:** CMHC premium tiers must be applied exactly as specified; any change requires a new migration and audit log entry.

### 3.5 OSFI B‑20 stress‑test & ratio validation (triggered on `submit`)

```python
qualifying_rate = max(contract_rate + Decimal('0.02'), Decimal('0.0525'))
# PITH = principal + interest + property tax + heating
pith = calculate_pith(qualifying_rate, requested_loan_amount, amortization_years, property_value)
gross_monthly_income = (client.annual_income + sum(cb.annual_income for cb in co_borrowers)) / 12
gds = pith / gross_monthly_income
tds = (pith + other_debt_payments) / gross_monthly_income

if gds > Decimal('0.39') or tds > Decimal('0.44'):
    raise BusinessRuleError("OSFI B‑20 ratios exceeded")
```

- **Audit logging:** The full calculation breakdown (`pith`, `gross_monthly_income`, `gds`, `tds`, `qualifying_rate`) is logged with `correlation_id` and stored in a separate `audit_underwriting_logs` table (see Migrations).
- **Compliance:** Hard limits of 39 % GDS and 44 % TDS must be enforced; any exception requires manual underwriter override and additional audit entry.

### 3.6 FINTRAC audit trail

- Every insert/update on `applications`, `clients`, `co_borrowers` creates an immutable record in `audit_fintrac_events` (see Migrations).
- **Transaction > $10 000:** If `requested_loan_amount` ≥ `10000`, the `transaction_type` column is set to `mortgage_application` and logged for FINTRAC reporting.
- **Retention:** 5‑year retention policy enforced at the database level (PostgreSQL row‑level security or archive partition).

---

## 4. Migrations

### 4.1 New tables

```sql
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    sin_encrypted BYTEA NOT NULL,
    date_of_birth DATE NOT NULL,  -- encrypted at rest via application layer
    employment_status VARCHAR(50) NOT NULL,
    employer_name VARCHAR(255),
    years_employed INT,
    annual_income NUMERIC(12,2) NOT NULL CHECK (annual_income > 0),
    other_income NUMERIC(12,2) DEFAULT 0,
    credit_score INT,
    marital_status VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_clients_user_id ON clients(user_id);
CREATE INDEX ix_clients_credit_score ON clients(credit_score);
CREATE INDEX ix_clients_created_at ON clients(created_at);

CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id),
    broker_id UUID REFERENCES users(id),
    application_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    property_address VARCHAR(255) NOT NULL,
    property_type VARCHAR(50) NOT NULL,
    property_value NUMERIC(12,2) NOT NULL CHECK (property_value > 0),
    purchase_price NUMERIC(12,2) NOT NULL CHECK (purchase_price > 0),
    down_payment NUMERIC(12,2) NOT NULL CHECK (down_payment > 0),
    requested_loan_amount NUMERIC(12,2) NOT NULL,
    amortization_years INT NOT NULL CHECK (amortization_years BETWEEN 5 AND 30),
    term_years INT NOT NULL CHECK (term_years BETWEEN 1 AND 10),
    mortgage_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ
);
CREATE INDEX ix_applications_client_id ON applications(client_id);
CREATE INDEX ix_applications_broker_id ON applications(broker_id);
CREATE INDEX ix_applications_status ON applications(status);
CREATE INDEX ix_applications_created_at ON applications(created_at);
CREATE INDEX ix_applications_submitted_at ON applications(submitted_at);

CREATE TABLE co_borrowers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    sin_encrypted BYTEA NOT NULL,
    annual_income NUMERIC(12,2) NOT NULL CHECK (annual_income > 0),
    employment_status VARCHAR(50) NOT NULL,
    credit_score INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_co_borrowers_application_id ON co_borrowers(application_id);
CREATE INDEX ix_co_borrowers_credit_score ON co_borrowers(credit_score);
```

### 4.2 Additional columns for compliance & business logic

```sql
ALTER TABLE applications
    ADD COLUMN insurance_required BOOLEAN DEFAULT FALSE,
    ADD COLUMN insurance_premium NUMERIC(12,2) DEFAULT 0,
    ADD COLUMN ltv_ratio NUMERIC(6,4),  -- loan / property value
    ADD COLUMN gds_ratio NUMERIC(6,4),
    ADD COLUMN tds_ratio NUMERIC(6,4),
    ADD COLUMN qualifying_rate NUMERIC(6,4);
```

### 4.3 Audit tables (FINTRAC & OSFI)

```sql
CREATE TABLE audit_fintrac_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(64) NOT NULL,
    record_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- INSERT, UPDATE
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID NOT NULL,  -- user_id from JWT
    transaction_type VARCHAR(50)  -- populated for loan_amount >= 10000
);
CREATE INDEX ix_audit_fintrac_record ON audit_fintrac_events(table_name, record_id);
CREATE INDEX ix_audit_fintrac_timestamp ON audit_fintrac_events(event_timestamp);

CREATE TABLE audit_underwriting_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id),
    calculation_step VARCHAR(100) NOT NULL,
    value JSONB NOT NULL,
    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    correlation_id VARCHAR(64) NOT NULL
);
CREATE INDEX ix_underwriting_app_id ON audit_underwriting_logs(application_id);
CREATE INDEX ix_underwriting_correlation ON audit_underwriting_logs(correlation_id);
```

### 4.4 Data migration

- **Initial seed:** None required; tables are empty at launch.
- **Future migration:** When encryption key rotation is introduced, a background job will re‑encrypt `sin_encrypted` fields with the new key version.

---

## 5. Security & Compliance

### 5.1 OSFI B‑20

- **Stress‑test rate:** `qualifying_rate = max(contract_rate + 2 %, 5.25 %)`.
- **Ratio caps:** GDS ≤ 39 %, TDS ≤ 44 %.
- **Audit:** Full breakdown logged to `audit_underwriting_logs` with `correlation_id` for every submission.
- **Implementation:** The `submit` service calls `underwriting.calculate_ratios()` and raises `BusinessRuleError` if limits are exceeded.

### 5.2 FINTRAC

- **Immutable audit:** All inserts/updates on `clients`, `applications`, `co_borrowers` generate a record in `audit_fintrac_events`.
- **Transaction flag:** If `requested_loan_amount >= 10000`, `transaction_type` is set to `mortgage_application`.
- **Retention:** PostgreSQL partition policy retains `audit_fintrac_events` for 5 years; older partitions are moved to archival storage.
- **Access:** Only compliance officers with `fintrac_viewer` role may query the audit table.

### 5.3 CMHC insurance

- **LTV calculation:** `ltv = requested_loan_amount / property_value` (4‑digit precision).
- **Premium tiers:** Applied exactly as per CMHC schedule (80.01‑85 % → 2.80 %, 85.01‑90 % → 3.10 %, 90.01‑95 % → 4.00 %).
- **Storage:** `insurance_required` (bool) and `insurance_premium` (Decimal) are persisted on the `applications` row.

### 5.4 PIPEDA

- **Encryption at rest:** `sin_encrypted` and `date_of_birth` are encrypted with AES‑256‑GCM before storage.
- **Never exposed:** SIN and DOB are omitted from all API responses, logs, and error messages.
- **Lookups:** Use SHA‑256 hash of SIN for duplicate checks (`sin_hash` column can be added later if needed).
- **Data minimization:** Only fields required for underwriting are collected; optional fields (`employer_name`, `years_employed`, `other_income`) are nullable.

### 5.5 Authentication & Authorization

- **JWT required** for all endpoints (see `common/security.verify_token()`).
- **Client role:** Can `POST`, `GET`, `PUT`, `submit` only applications where `client_id` matches the JWT `sub`.
- **Broker role:** Can `POST`, `GET`, `PUT`, `submit` applications where `broker_id` matches the JWT `sub` or `client_id` belongs to one of the broker’s clients (relationship enforced in service layer).
- **Admin role:** Full access (not used in this module).

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `ApplicationNotFoundError` | 404 | `INTAKE_001` | `Application {id} not found` | `GET /applications/{id}` with non‑existent UUID |
| `ApplicationValidationError` | 422 | `INTAKE_002` | `{field}: {reason}` | `amortization_years` > 30 |
| `ApplicationBusinessRuleError` | 409 | `INTAKE_003` | `{rule} violated: {detail}` | Submitting non‑draft application |
| `ApplicationConflictError` | 409 | `INTAKE_004` | `Resource conflict: {detail}` | Duplicate SIN within same application |
| `UnauthorizedError` | 401 | `AUTH_001` | `Authentication required` | Missing JWT |
| `ForbiddenError` | 403 | `AUTH_002` | `Insufficient permissions` | Client trying to access another client’s app |

**Implementation notes**

- All exceptions inherit from `common.exceptions.AppException` and are caught by a global FastAPI exception handler that returns the structured JSON: `{"detail": "...", "error_code": "..."}`.
- `ApplicationValidationError` is raised by Pydantic validation (FastAPI) **and** by manual checks in the service layer (e.g., down‑payment percentage).
- `ApplicationBusinessRuleError` is raised when OSFI B‑20 ratios exceed limits, or when a transition is invalid.

---

## 7. Future Enhancements (Out of Scope for Initial Design)

- **SIN hash column** for fast duplicate detection across clients.
- **Key rotation** API endpoint for encryption keys.
- **Co‑borrower separate endpoint** (`/applications/{id}/co‑borrowers`) for fine‑grained management.
- **Document upload** integration (e.g., proof of income) with secure storage.
- **Webhook** on status change to notify broker/client.

---

**End of Design Document**
```