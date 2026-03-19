# Client Intake & Application
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Client Intake & Application Module Design

**Design Doc Location:** `docs/design/client-intake-application.md`  
**Module Identifier:** `CLIENT_INTAKE`  
**Last Updated:** 2024

---

## 1. Endpoints

### `POST /api/v1/applications`
Create a new mortgage application (draft status).

**Request Body Schema:**
```json
{
  "client_id": "uuid",  // required, must match authenticated user or be assignable by broker
  "application_type": "purchase|refinance|renewal",  // required
  "property_address": {
    "street": "string",  // required
    "city": "string",  // required
    "province": "string",  // required, 2-letter code
    "postal_code": "string",  // required, A1A 1A1 format
    "country": "string"  // default: "Canada"
  },
  "property_type": "single_family|condo|townhouse|multi_unit",  // required
  "property_value": "decimal",  // required, > 0
  "purchase_price": "decimal",  // required for purchase, > 0
  "down_payment": "decimal",  // required for purchase, >= 0
  "requested_loan_amount": "decimal",  // required, > 0
  "amortization_years": "integer",  // required, 5-30 (insured) or 5-25 (uninsured)
  "term_years": "integer",  // required, 1-10
  "mortgage_type": "fixed|variable|adjustable",  // required
  "co_borrowers": [  // optional
    {
      "full_name": "string",  // required
      "sin": "string",  // required, 9 digits, encrypted at rest
      "annual_income": "decimal",  // required, > 0
      "employment_status": "employed|self_employed|unemployed|retired",  // required
      "credit_score": "integer"  // optional, 300-900
    }
  ]
}
```

**Response Schema (201):**
```json
{
  "id": "uuid",
  "client_id": "uuid",
  "broker_id": "uuid|null",
  "application_type": "string",
  "status": "draft",
  "property_address": { "object" },
  "property_type": "string",
  "property_value": "decimal",
  "purchase_price": "decimal|null",
  "down_payment": "decimal|null",
  "requested_loan_amount": "decimal",
  "amortization_years": "integer",
  "term_years": "integer",
  "mortgage_type": "string",
  "ltv_ratio": "decimal",  // calculated
  "insurance_required": "boolean",  // calculated
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Error Responses:**
- `422` CLIENT_INTAKE_002: Validation failure (e.g., amortization out of range, negative income)
- `404` CLIENT_INTAKE_001: Client profile not found for user_id
- `409` CLIENT_INTAKE_003: Duplicate active application for same property
- `403` CLIENT_INTAKE_004: Authenticated user lacks permission to create application for this client

**Auth:** Authenticated (JWT) - Client or Broker

---

### `GET /api/v1/applications`
List applications with pagination and filtering.

**Query Parameters:**
- `status`: string (optional, filter by status)
- `page`: integer (default: 1)
- `limit`: integer (default: 20, max: 100)

**Response Schema (200):**
```json
{
  "items": [
    {
      "id": "uuid",
      "application_type": "string",
      "status": "string",
      "property_address": { "city": "string", "province": "string" },
      "property_value": "decimal",
      "requested_loan_amount": "decimal",
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ],
  "total": "integer",
  "page": "integer",
  "limit": "integer"
}
```

**Error Responses:**
- `403` CLIENT_INTAKE_004: Access denied if user role cannot list applications

**Auth:** Authenticated - Client sees own, Broker sees assigned, Admin sees all

---

### `GET /api/v1/applications/{id}`
Retrieve a single application by ID.

**Response Schema (200):** Same as POST response, plus:
```json
{
  "co_borrowers": [
    {
      "id": "uuid",
      "full_name": "string",
      "annual_income": "decimal",
      "employment_status": "string",
      "credit_score": "integer|null"
      // SIN and DOB never returned
    }
  ]
}
```

**Error Responses:**
- `404` CLIENT_INTAKE_001: Application not found
- `403` CLIENT_INTAKE_004: User lacks access to this application

**Auth:** Authenticated - Must be owner client, assigned broker, or admin

---

### `PUT /api/v1/applications/{id}`
Update an application (draft status only).

**Request Body Schema:** Same as POST, but all fields optional except `client_id`.

**Response Schema (200):** Full application object (same as GET)

**Error Responses:**
- `404` CLIENT_INTAKE_001: Application not found
- `403` CLIENT_INTAKE_004: Access denied
- `409` CLIENT_INTAKE_005: Cannot update application in non-draft status
- `422` CLIENT_INTAKE_002: Validation failure

**Auth:** Authenticated - Must be owner client or assigned broker

---

### `POST /api/v1/applications/{id}/submit`
Submit application for underwriting review.

**Request Body Schema:**
```json
{
  "declarations": {
    "information_accuracy": "boolean",  // required, must be true
    "consent_to_credit_check": "boolean",  // required, must be true
    "consent_to_disclosure": "boolean"  // required, must be true
  }
}
```

**Response Schema (200):**
```json
{
  "id": "uuid",
  "status": "submitted",
  "submitted_at": "datetime",
  "next_steps": "string"
}
```

**Error Responses:**
- `422` CLIENT_INTAKE_002: Declarations not accepted
- `409` CLIENT_INTAKE_005: Application already submitted or invalid state
- `403` CLIENT_INTAKE_004: Access denied

**Auth:** Authenticated - Must be owner client or assigned broker

---

### `GET /api/v1/applications/{id}/summary`
Retrieve PDF-ready JSON summary for document generation.

**Response Schema (200):**
```json
{
  "application_id": "uuid",
  "generated_at": "datetime",
  "client": {
    "user_id": "uuid",
    "employment_status": "string",
    "employer_name": "string",
    "years_employed": "integer",
    "annual_income": "decimal",
    "other_income": "decimal",
    "credit_score": "integer",
    "marital_status": "string"
    // SIN and DOB excluded
  },
  "co_borrowers": [ "array of sanitized objects" ],
  "property": {
    "address": { "object" },
    "type": "string",
    "value": "decimal",
    "purchase_price": "decimal|null"
  },
  "loan_details": {
    "requested_amount": "decimal",
    "down_payment": "decimal|null",
    "ltv_ratio": "decimal",
    "insurance_required": "boolean",
    "amortization_years": "integer",
    "term_years": "integer",
    "mortgage_type": "string"
  },
  "declarations": { "object" }
}
```

**Error Responses:**
- `404` CLIENT_INTAKE_001: Application not found
- `403` CLIENT_INTAKE_004: Access denied

**Auth:** Authenticated - Must be owner client, assigned broker, or admin

---

## 2. Models & Database

### `clients` Table
Store client PII and financial profile. **CRITICAL**: All PII encrypted.

| Column | Type | Constraints | Index | Encrypted |
|--------|------|-------------|-------|-----------|
| `id` | UUID | PK, default gen_random_uuid() | Primary | No |
| `user_id` | UUID | FK → users.id, not null | Unique, FK | No |
| `sin_encrypted` | LargeBinary | not null | - | **YES** |
| `sin_hash` | VARCHAR(64) | not null, unique | Unique | No (SHA256) |
| `date_of_birth_encrypted` | LargeBinary | not null | - | **YES** |
| `employment_status` | VARCHAR(50) | not null | - | No |
| `employer_name` | VARCHAR(255) | - | - | No |
| `years_employed` | INTEGER | >= 0 | - | No |
| `annual_income` | DECIMAL(12,2) | not null, > 0 | - | No |
| `other_income` | DECIMAL(12,2) | default 0 | - | No |
| `credit_score` | INTEGER | 300-900 | - | No |
| `marital_status` | VARCHAR(50) | - | - | No |
| `created_at` | TIMESTAMP | not null, default now() | Composite | No |
| `updated_at` | TIMESTAMP | not null, default now(), onupdate | Composite | No |

**Indexes:**
- `idx_clients_user_id` (user_id)
- `idx_clients_sin_hash` (sin_hash) - for duplicate checking
- `idx_clients_created_at` (created_at DESC)

**Relationships:**
- One-to-One with `users` table via `user_id`

---

### `applications` Table
Core mortgage application data.

| Column | Type | Constraints | Index | Notes |
|--------|------|-------------|-------|-------|
| `id` | UUID | PK | Primary | - |
| `client_id` | UUID | FK → clients.id, not null | Composite FK | - |
| `broker_id` | UUID | FK → users.id, nullable | Composite FK | - |
| `application_type` | VARCHAR(50) | not null | - | Enum: purchase, refinance, renewal |
| `status` | VARCHAR(50) | not null, default 'draft' | Composite | Enum: draft, submitted, underwriting, approved, rejected, cancelled |
| `property_address` | JSONB | not null | GIN | Structured address |
| `property_type` | VARCHAR(50) | not null | - | Enum: single_family, condo, townhouse, multi_unit |
| `property_value` | DECIMAL(12,2) | not null, > 0 | - | Current/appraised value |
| `purchase_price` | DECIMAL(12,2) | nullable, > 0 | - | For purchase apps only |
| `down_payment` | DECIMAL(12,2) | nullable, >= 0 | - | For purchase apps only |
| `requested_loan_amount` | DECIMAL(12,2) | not null, > 0 | - | - |
| `amortization_years` | INTEGER | not null, 5-30 | - | Constrained by insurance status |
| `term_years` | INTEGER | not null, 1-10 | - | - |
| `mortgage_type` | VARCHAR(50) | not null | - | Enum: fixed, variable, adjustable |
| `created_at` | TIMESTAMP | not null, default now() | Composite | Audit |
| `updated_at` | TIMESTAMP | not null, default now(), onupdate | Composite | Audit |
| `submitted_at` | TIMESTAMP | nullable | - | Set on submit |

**Indexes:**
- `idx_applications_client_status` (client_id, status) - for client queries
- `idx_applications_broker_status` (broker_id, status) - for broker queues
- `idx_applications_status_created` (status, created_at DESC) - for underwriting queue
- `gin_idx_property_address` (property_address) - for address search

**Relationships:**
- Many-to-One with `clients` (client_id)
- Many-to-One with `users` (broker_id)
- One-to-Many with `co_borrowers` (application_id)

---

### `co_borrowers` Table
Co-borrower details for joint applications.

| Column | Type | Constraints | Index | Encrypted |
|--------|------|-------------|-------|-----------|
| `id` | UUID | PK | Primary | No |
| `application_id` | UUID | FK → applications.id, not null | Composite FK | No |
| `full_name` | VARCHAR(255) | not null | - | No |
| `sin_encrypted` | LargeBinary | not null | - | **YES** |
| `sin_hash` | VARCHAR(64) | not null | - | No (SHA256) |
| `annual_income` | DECIMAL(12,2) | not null, > 0 | - | No |
| `employment_status` | VARCHAR(50) | not null | - | No |
| `credit_score` | INTEGER | 300-900 | - | No |
| `created_at` | TIMESTAMP | not null, default now() | - | No |
| `updated_at` | TIMESTAMP | not null, default now(), onupdate | - | No |

**Indexes:**
- `idx_coborrowers_application_id` (application_id)
- `idx_coborrowers_sin_hash` (sin_hash) - for duplicate detection

**Relationships:**
- Many-to-One with `applications` (application_id)

---

## 3. Business Logic

### State Machine Transitions

```
[draft] ──submit()──► [submitted] ──start_underwriting()──► [underwriting]
  │                       │
  │ update()              │ cancel()
  │                       ▼
  └──────────────────► [cancelled]

[underwriting] ──approve()──► [approved]
   │                         │
   │ reject()                │ require_changes()
   ▼                         ▼
[rejected]                [underwriting] (loop)
```

**Transition Rules:**
- **draft → submitted**: All validations pass, declarations signed, triggers FINTRAC audit log
- **submitted → underwriting**: Underwriter assigns to self, locks application for editing
- **underwriting → approved/rejected**: Underwriting decision made, triggers CMHC insurance calculation if LTV > 80%
- **Any → cancelled**: Only by client/broker before approval, requires cancellation reason

### Validation Algorithms

**LTV Calculation:**
```python
ltv_ratio = (requested_loan_amount / property_value) * 100
# Use Decimal precision, rounded to 2 decimal places
```

**CMHC Insurance Requirement:**
```python
if ltv_ratio > 80.00:
    insurance_required = True
    premium_rate = lookup_cmhc_premium(ltv_ratio)  # 2.80%, 3.10%, or 4.00%
    insurance_premium = requested_loan_amount * (premium_rate / 100)
else:
    insurance_required = False
    insurance_premium = 0
```

**Amortization Validation:**
```python
if insurance_required:
    max_amortization = 30
else:
    max_amortization = 25  # CMHC uninsured maximum

if not (5 <= amortization_years <= max_amortization):
    raise ValidationError(f"Amortization must be 5-{max_amortization} years")
```

**Income Validation:**
```python
total_household_income = client.annual_income + sum(cb.annual_income for cb in co_borrowers)
if total_household_income <= 0:
    raise ValidationError("Total household income must be greater than 0")
```

### Co-borrower Management

- Co-borrowers can only be added/modified when `status = 'draft'`
- On application submit, co-borrower data is frozen and hashed for audit
- Maximum 3 co-borrowers per application (business rule)
- Co-borrower SIN must be unique across active applications (duplicate check via `sin_hash`)

---

## 4. Migrations

### New Tables
```sql
-- Table: clients
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) UNIQUE,
    sin_encrypted BYTEA NOT NULL,
    sin_hash VARCHAR(64) NOT NULL UNIQUE,
    date_of_birth_encrypted BYTEA NOT NULL,
    employment_status VARCHAR(50) NOT NULL,
    employer_name VARCHAR(255),
    years_employed INTEGER CHECK (years_employed >= 0),
    annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
    other_income DECIMAL(12,2) DEFAULT 0,
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    marital_status VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Table: applications
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id),
    broker_id UUID REFERENCES users(id),
    application_type VARCHAR(50) NOT NULL CHECK (application_type IN ('purchase', 'refinance', 'renewal')),
    status VARCHAR(50) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'underwriting', 'approved', 'rejected', 'cancelled')),
    property_address JSONB NOT NULL,
    property_type VARCHAR(50) NOT NULL,
    property_value DECIMAL(12,2) NOT NULL CHECK (property_value > 0),
    purchase_price DECIMAL(12,2) CHECK (purchase_price > 0),
    down_payment DECIMAL(12,2) CHECK (down_payment >= 0),
    requested_loan_amount DECIMAL(12,2) NOT NULL CHECK (requested_loan_amount > 0),
    amortization_years INTEGER NOT NULL CHECK (amortization_years BETWEEN 5 AND 30),
    term_years INTEGER NOT NULL CHECK (term_years BETWEEN 1 AND 10),
    mortgage_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMP
);

-- Table: co_borrowers
CREATE TABLE co_borrowers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    sin_encrypted BYTEA NOT NULL,
    sin_hash VARCHAR(64) NOT NULL,
    annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
    employment_status VARCHAR(50) NOT NULL,
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### Indexes
```sql
CREATE INDEX idx_clients_user_id ON clients(user_id);
CREATE INDEX idx_clients_sin_hash ON clients(sin_hash);
CREATE INDEX idx_applications_client_status ON applications(client_id, status);
CREATE INDEX idx_applications_broker_status ON applications(broker_id, status);
CREATE INDEX idx_applications_status_created ON applications(status, created_at DESC);
CREATE INDEX gin_idx_property_address ON applications USING GIN(property_address);
CREATE INDEX idx_coborrowers_application_id ON co_borrowers(application_id);
CREATE INDEX idx_coborrowers_sin_hash ON co_borrowers(sin_hash);
```

### Data Migration
- **Scenario:** If migrating from legacy system, populate `clients` table from existing `users` table
- **Steps:**
  1. Generate `sin_hash` from plaintext SIN (one-time operation)
  2. Encrypt SIN/DOB using AES-256 with KMS-derived key
  3. Backfill `annual_income` from last known tax records
  4. Set `created_at` from legacy `registration_date`
- **Rollback:** Maintain parallel tables for 30-day verification period

---

## 5. Security & Compliance

### OSFI B-20 Requirements
- **Data Collection:** Module must capture all inputs required for GDS/TDS calculation:
  - PITH components (Principal, Interest, Taxes, Heating)
  - Gross monthly income (client + co-borrowers)
  - Other debt obligations (to be collected in Liabilities module)
- **Stress Test:** Qualifying rate = `max(contract_rate + 2%, 5.25%)` - calculated in underwriting module
- **Audit Trail:** Log calculation inputs with `correlation_id` for regulator review

### FINTRAC Reporting Triggers
- **Threshold:** `requested_loan_amount > CAD 10,000` (always true for mortgages)
- **Mandatory Fields:** All applications automatically flagged as `large_transaction = True`
- **Audit Log:** On submit, create immutable record in `fintrac_reports` table:
  ```sql
  INSERT INTO fintrac_reports (application_id, transaction_type, amount, client_id, created_by)
  VALUES ($1, 'mortgage_application', $2, $3, $4);
  ```
- **Retention:** 5-year retention enforced via PostgreSQL row-level security policies

### PIPEDA Data Handling
- **Encryption:** AES-256-GCM for `sin_encrypted` and `date_of_birth_encrypted`
  - Key Management: Envelope encryption with AWS KMS (or Azure Key Vault)
  - Data Key: Unique per record, encrypted with KMS master key
  - Rotation: Automatic on write operations, master key rotated annually
- **Hashing:** SHA-256 with salt for `sin_hash` (used for duplicate checks)
- **Logging:** Strict structlog filters to redact:
  - `sin`, `date_of_birth`, `annual_income`, `other_income`, `credit_score`
  - Use `log.bind(sin_hash=sin_hash[:8])` for debugging only
- **API Response:** SIN and DOB never serialized in Pydantic schemas (exclude=True)

### Authentication & Authorization Matrix

| Endpoint | Client | Broker | Admin |
|----------|--------|--------|-------|
| POST /applications | Own only | Assignable | Yes |
| GET /applications | Own only | Assigned only | All |
| GET /applications/{id} | Own only | Assigned only | All |
| PUT /applications/{id} | Own draft only | Assigned draft only | Yes |
| POST /applications/{id}/submit | Own draft only | Assigned draft only | Yes |
| GET /applications/{id}/summary | Own only | Assigned only | All |

**Implementation:** Use FastAPI dependencies:
- `get_current_user()` → JWT token validation
- `verify_application_ownership(application_id: UUID)` → Raises 403 if unauthorized

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `ClientIntakeNotFoundError` | 404 | CLIENT_INTAKE_001 | "Application {id} not found" | GET non-existent UUID |
| `ClientIntakeValidationError` | 422 | CLIENT_INTAKE_002 | "{field}: {reason}" | amortization_years=35 |
| `ClientIntakeBusinessRuleError` | 409 | CLIENT_INTAKE_003 | "{rule} violated: {detail}" | LTV > 95% (uninsured) |
| `ClientIntakeAccessDeniedError` | 403 | CLIENT_INTAKE_004 | "Access denied to application {id}" | Client viewing broker's app |
| `ClientIntakeInvalidStateError` | 409 | CLIENT_INTAKE_005 | "Cannot {action} in {status} status" | Update submitted app |
| `ClientIntakeDuplicateError` | 409 | CLIENT_INTAKE_006 | "Duplicate SIN hash detected" | SIN already in active app |
| `ClientIntakeEncryptionError` | 500 | CLIENT_INTAKE_007 | "Failed to encrypt PII data" | KMS unavailable |

**Error Response Format (consistent across all endpoints):**
```json
{
  "detail": "Application 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "CLIENT_INTAKE_001",
  "correlation_id": "corr_01HQX...",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

**Implementation Notes:**
- All exceptions inherit from `common.exceptions.AppException`
- Use FastAPI exception handlers to map to structured JSON
- Log errors with `structlog` including `error_code` and `correlation_id`
- Never include PII in error messages or logs

---

## Missing Details Resolution

### Application Status Workflow
**States:** `draft`, `submitted`, `underwriting`, `approved`, `rejected`, `cancelled`  
**Transitions:** Defined in Business Logic section with guard conditions

### Default Types & Enums
```python
# application_type: purchase, refinance, renewal
# mortgage_type: fixed, variable, adjustable
# property_type: single_family, condo, townhouse, multi_unit
# employment_status: employed, self_employed, unemployed, retired
# marital_status: single, married, common_law, divorced, widowed
```

### Co-borrower Management
- **Add/Remove:** Via PUT /applications/{id} when status=draft
- **Validation:** Max 3 co-borrowers, unique SIN per application
- **Cascade:** On application delete, co_borrowers deleted (ON DELETE CASCADE)

### SIN Encryption Key Management
**Envelope Encryption Pattern:**
1. Generate unique DEK (Data Encryption Key) per record
2. Encrypt PII fields with DEK using AES-256-GCM
3. Encrypt DEK with KMS master key (KEK - Key Encryption Key)
4. Store: `sin_encrypted = encrypted_data + nonce + encrypted_dek`
5. KMS master key rotation: Annual or on security event
6. Access logging: All KMS decrypt calls logged for audit

---

## Regulatory Checklist

- [ ] OSFI B-20: All GDS/TDS inputs captured and logged
- [ ] FINTRAC: Large transaction flag set, audit log created on submit
- [ ] CMHC: LTV and insurance premium calculated on submit
- [ ] PIPEDA: SIN/DOB encrypted, never in logs/responses, data minimization enforced
- [ ] All models include `created_at`, `updated_at` audit fields
- [ ] Decimal types used for all financial values (no float)
- [ ] Immutable audit trail maintained (no updates after submit)