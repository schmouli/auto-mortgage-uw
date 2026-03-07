# Design: Client Intake & Application
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Design Plan: Client Intake & Application Module

**Feature Slug:** `client-intake-application`  
**Module Path:** `modules/client_intake/`  
**Design Document:** `docs/design/client-intake-application.md`

---

## 1. Endpoints

### `POST /api/v1/applications`
Create a new mortgage application (draft status).

**Authentication:** Authenticated client or broker  
**Authorization:** Client can create only for self; broker can create for assigned clients

**Request Body Schema:**
```json
{
  "client_id": "uuid",                      // required, must match auth user or be assignable
  "application_type": "enum[purchase, refinance, renewal]", // required
  "property_address": "str",                // required, encrypted at rest
  "property_type": "enum[single_family, condo, townhouse, multi_unit]", // required
  "property_value": "Decimal(12,2)",        // required > 0
  "purchase_price": "Decimal(12,2)",        // required > 0
  "down_payment": "Decimal(12,2)",          // required ≥ 5% of purchase_price
  "requested_loan_amount": "Decimal(12,2)", // required = purchase_price - down_payment
  "amortization_years": "int",              // required: 5-30 (insured), 5-25 (uninsured)
  "term_years": "int",                      // required: 1-10
  "mortgage_type": "enum[fixed, variable, adjustable]", // required
  "interest_rate": "Decimal(5,3)",          // optional, defaults to market rate
  "co_borrowers": [                         // optional
    {
      "full_name": "str",                   // required
      "sin": "str",                         // required, encrypted
      "annual_income": "Decimal(12,2)",     // required > 0
      "employment_status": "enum[employed, self_employed, unemployed, retired]", // required
      "credit_score": "int"                 // optional
    }
  ]
}
```

**Response Schema (201 Created):**
```json
{
  "id": "uuid",
  "client_id": "uuid",
  "status": "draft",
  "property_address_hash": "str",           // SHA256 hash for verification
  "property_value": "Decimal(12,2)",
  "purchase_price": "Decimal(12,2)",
  "down_payment": "Decimal(12,2)",
  "requested_loan_amount": "Decimal(12,2)",
  "ltv_ratio": "Decimal(5,2)",              // Calculated: loan / property_value
  "insurance_required": "bool",             // CMHC: true if LTV > 80%
  "insurance_premium": "Decimal(12,2)",     // If applicable, per CMHC tiers
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Error Responses:**
- `400 Bad Request` → `CLIENT_INTAKE_002` - Validation error (e.g., down payment < 5%)
- `400 Bad Request` → `CLIENT_INTAKE_003` - Business rule violation (LTV > 95%)
- `401 Unauthorized` → `SECURITY_001` - Invalid/missing token
- `403 Forbidden` → `CLIENT_INTAKE_004` - Client not authorized to create for this user
- `422 Unprocessable Entity` → `CLIENT_INTAKE_002` - Field format invalid (e.g., SIN format)

---

### `GET /api/v1/applications`
List applications with pagination and filtering.

**Authentication:** Authenticated client or broker  
**Authorization:** Clients see own apps; brokers see assigned apps only

**Query Parameters:**
- `status: str` - Filter by status
- `page: int` - Page number (default: 1)
- `page_size: int` - Items per page (default: 20, max: 100)

**Response Schema (200 OK):**
```json
{
  "items": [
    {
      "id": "uuid",
      "status": "enum",
      "property_address_hash": "str",
      "property_value": "Decimal(12,2)",
      "purchase_price": "Decimal(12,2)",
      "requested_loan_amount": "Decimal(12,2)",
      "created_at": "datetime",
      "updated_at": "datetime",
      "submitted_at": "datetime|null"
    }
  ],
  "total": "int",
  "page": "int",
  "page_size": "int"
}
```

**Error Responses:**
- `401 Unauthorized` → `SECURITY_001`
- `403 Forbidden` → `CLIENT_INTAKE_004` - Access to unauthorized application

---

### `GET /api/v1/applications/{id}`
Get single application details.

**Authentication:** Authenticated client or broker  
**Authorization:** Must be owner client or assigned broker

**Response Schema (200 OK):**
```json
{
  "id": "uuid",
  "client_id": "uuid",
  "broker_id": "uuid|null",
  "status": "enum",
  "property_address_hash": "str",
  "property_type": "enum",
  "property_value": "Decimal(12,2)",
  "purchase_price": "Decimal(12,2)",
  "down_payment": "Decimal(12,2)",
  "requested_loan_amount": "Decimal(12,2)",
  "amortization_years": "int",
  "term_years": "int",
  "mortgage_type": "enum",
  "interest_rate": "Decimal(5,3)",
  "ltv_ratio": "Decimal(5,2)",
  "insurance_required": "bool",
  "insurance_premium": "Decimal(12,2)",
  "co_borrowers": [
    {
      "id": "uuid",
      "full_name": "str",
      "annual_income": "Decimal(12,2)",
      "employment_status": "enum",
      "credit_score": "int|null"
    }
  ],
  "created_at": "datetime",
  "updated_at": "datetime",
  "submitted_at": "datetime|null"
}
```
**Note:** SIN, DOB, and raw property address are **never** returned.

**Error Responses:**
- `401 Unauthorized` → `SECURITY_001`
- `403 Forbidden` → `CLIENT_INTAKE_004`
- `404 Not Found` → `CLIENT_INTAKE_001` - Application not found

---

### `PUT /api/v1/applications/{id}`
Update draft application. Only allowed in `draft` or `rejected` status.

**Authentication:** Authenticated client or broker  
**Authorization:** Must be owner client or assigned broker

**Request Body Schema:** Same as POST (excluding co_borrowers array; use separate endpoints for co-borrower management)

**Response Schema (200 OK):** Same as GET /applications/{id}

**Error Responses:**
- `400 Bad Request` → `CLIENT_INTAKE_003` - Cannot update non-draft/rejected application
- `401 Unauthorized` → `SECURITY_001`
- `403 Forbidden` → `CLIENT_INTAKE_004`
- `404 Not Found` → `CLIENT_INTAKE_001`
- `422 Unprocessable Entity` → `CLIENT_INTAKE_002`

---

### `POST /api/v1/applications/{id}/submit`
Submit application for underwriting review. Triggers compliance checks and status transition.

**Authentication:** Authenticated client or broker  
**Authorization:** Must be owner client or assigned broker

**Request Body:** `none` (all data from application record)

**Response Schema (202 Accepted):**
```json
{
  "id": "uuid",
  "status": "submitted",
  "submitted_at": "datetime",
  "compliance_checks": {
    "gds_ratio": "Decimal(5,2)",      // Gross Debt Service
    "tds_ratio": "Decimal(5,2)",      // Total Debt Service
    "stress_test_rate": "Decimal(5,3)", // OSFI B-20 qualifying rate
    "gds_within_limit": "bool",       // Must be ≤ 39%
    "tds_within_limit": "bool",       // Must be ≤ 44%
    "cmhc_insurance_required": "bool",
    "fintrac_reportable": "bool"      // True if loan_amount ≥ $10,000
  }
}
```

**Error Responses:**
- `400 Bad Request` → `CLIENT_INTAKE_003` - GDS/TDS exceeds OSFI limits
- `400 Bad Request` → `CLIENT_INTAKE_003` - Missing required fields
- `401 Unauthorized` → `SECURITY_001`
- `403 Forbidden` → `CLIENT_INTAKE_004`
- `404 Not Found` → `CLIENT_INTAKE_001`
- `409 Conflict` → `CLIENT_INTAKE_005` - Invalid status transition

---

### `GET /api/v1/applications/{id}/summary`
Get PDF-ready JSON for final application summary (audit/printing).

**Authentication:** Authenticated client or broker  
**Authorization:** Must be owner client or assigned broker

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "generated_at": "datetime",
  "client": {
    "user_id": "uuid",
    "employment_status": "enum",
    "years_employed": "Decimal(4,1)",
    "annual_income": "Decimal(12,2)",
    "other_income": "Decimal(12,2)",
    "credit_score": "int",
    "marital_status": "enum"
  },
  "property": {
    "address_hash": "str",
    "type": "enum",
    "value": "Decimal(12,2)",
    "purchase_price": "Decimal(12,2)"
  },
  "mortgage": {
    "loan_amount": "Decimal(12,2)",
    "down_payment": "Decimal(12,2)",
    "ltv_ratio": "Decimal(5,2)",
    "amortization_years": "int",
    "term_years": "int",
    "mortgage_type": "enum",
    "interest_rate": "Decimal(5,3)",
    "insurance_required": "bool",
    "insurance_premium": "Decimal(12,2)"
  },
  "co_borrowers": [
    {
      "full_name": "str",
      "annual_income": "Decimal(12,2)",
      "employment_status": "enum",
      "credit_score": "int"
    }
  ],
  "compliance": {
    "gds_ratio": "Decimal(5,2)",
    "tds_ratio": "Decimal(5,2)",
    "stress_test_rate": "Decimal(5,3)",
    "osfi_b20_compliant": "bool"
  },
  "audit_trail": {
    "created_at": "datetime",
    "submitted_at": "datetime",
    "created_by": "uuid"
  }
}
```

**Error Responses:**
- `401 Unauthorized` → `SECURITY_001`
- `403 Forbidden` → `CLIENT_INTAKE_004`
- `404 Not Found` → `CLIENT_INTAKE_001`

---

## 2. Models & Database

### `clients` Table
**Table Name:** `clients`  
**Purpose:** Store client PII and financial profile

| Column | Type | Constraints | Index | Encrypted | Notes |
|--------|------|-------------|-------|-----------|-------|
| `id` | `UUID` | PK, default gen_random_uuid() | - | No | |
| `user_id` | `UUID` | FK → users.id, NOT NULL | ✓ (single) | No | For authz |
| `sin_encrypted` | `BYTEA` | NOT NULL | No | ✓ AES-256 | |
| `sin_hash` | `VARCHAR(64)` | NOT NULL, UNIQUE | ✓ (single) | No | SHA256 for lookups |
| `date_of_birth_encrypted` | `BYTEA` | NOT NULL | No | ✓ AES-256 | |
| `employment_status` | `employment_status_enum` | NOT NULL | ✓ (single) | No | `employed, self_employed, unemployed, retired` |
| `employer_name` | `VARCHAR(255)` | - | No | No | |
| `years_employed` | `DECIMAL(4,1)` | CHECK ≥ 0 | No | No | |
| `annual_income` | `DECIMAL(12,2)` | NOT NULL, CHECK > 0 | ✓ (single) | No | **Never log** |
| `other_income` | `DECIMAL(12,2)` | DEFAULT 0, CHECK ≥ 0 | No | No | **Never log** |
| `credit_score` | `INTEGER` | CHECK 300-900 | ✓ (single) | No | |
| `marital_status` | `marital_status_enum` | NOT NULL | No | No | `single, married, common_law, divorced, widowed` |
| `created_at` | `TIMESTAMP` | NOT NULL, default now() | ✓ (composite) | No | Audit |
| `updated_at` | `TIMESTAMP` | NOT NULL, default now() | ✓ (composite) | No | Audit |

**Indexes:**
- `idx_clients_user_id` ON (`user_id`)
- `idx_clients_sin_hash` ON (`sin_hash`) UNIQUE
- `idx_clients_created_at` ON (`created_at`)

**Relationships:**
- Many-to-One: `clients.user_id` → `users.id`

---

### `applications` Table
**Table Name:** `applications`  
**Purpose:** Store mortgage application details and state

| Column | Type | Constraints | Index | Encrypted | Notes |
|--------|------|-------------|-------|-----------|-------|
| `id` | `UUID` | PK, default gen_random_uuid() | - | No | |
| `client_id` | `UUID` | FK → clients.id, NOT NULL | ✓ (single) | No | |
| `broker_id` | `UUID` | FK → users.id, NULLABLE | ✓ (single) | No | NULL until assigned |
| `application_type` | `application_type_enum` | NOT NULL | ✓ (single) | No | `purchase, refinance, renewal` |
| `status` | `application_status_enum` | NOT NULL, default 'draft' | ✓ (composite) | No | See workflow below |
| `property_address_encrypted` | `TEXT` | NOT NULL | No | ✓ AES-256 | PIPEDA-protected |
| `property_type` | `property_type_enum` | NOT NULL | ✓ (single) | No | |
| `property_value` | `DECIMAL(12,2)` | NOT NULL, CHECK > 0 | ✓ (single) | No | |
| `purchase_price` | `DECIMAL(12,2)` | NOT NULL, CHECK > 0 | ✓ (single) | No | FINTRAC trigger |
| `down_payment` | `DECIMAL(12,2)` | NOT NULL, CHECK ≥ 0 | No | No | |
| `requested_loan_amount` | `DECIMAL(12,2)` | NOT NULL, CHECK > 0 | ✓ (single) | No | **Never log** |
| `amortization_years` | `INTEGER` | NOT NULL, CHECK 5-30 | ✓ (single) | No | CMHC rule |
| `term_years` | `INTEGER` | NOT NULL, CHECK 1-10 | No | No | |
| `mortgage_type` | `mortgage_type_enum` | NOT NULL | No | No | `fixed, variable, adjustable` |
| `interest_rate` | `DECIMAL(5,3)` | NOT NULL, CHECK > 0 | No | No | |
| `created_at` | `TIMESTAMP` | NOT NULL, default now() | ✓ (composite) | No | Audit |
| `updated_at` | `TIMESTAMP` | NOT NULL, default now() | ✓ (composite) | No | Audit |
| `submitted_at` | `TIMESTAMP` | NULLABLE | ✓ (single) | No | Set on submit |

**Indexes:**
- `idx_applications_client_id` ON (`client_id`)
- `idx_applications_broker_id` ON (`broker_id`)
- `idx_applications_status_created_at` ON (`status`, `created_at` DESC)
- `idx_applications_submitted_at` ON (`submitted_at`) WHERE submitted_at IS NOT NULL
- `idx_applications_loan_amount` ON (`requested_loan_amount`) FOR FINTRAC queries

**Relationships:**
- Many-to-One: `applications.client_id` → `clients.id`
- Many-to-One: `applications.broker_id` → `users.id`
- One-to-Many: `applications.id` → `co_borrowers.application_id`

---

### `co_borrowers` Table
**Table Name:** `co_borrowers`  
**Purpose:** Store co-borrower financial data for joint applications

| Column | Type | Constraints | Index | Encrypted | Notes |
|--------|------|-------------|-------|-----------|-------|
| `id` | `UUID` | PK, default gen_random_uuid() | - | No | |
| `application_id` | `UUID` | FK → applications.id, NOT NULL | ✓ (single) | No | Cascade delete |
| `full_name` | `VARCHAR(255)` | NOT NULL | No | No | |
| `sin_encrypted` | `BYTEA` | NOT NULL | No | ✓ AES-256 | |
| `sin_hash` | `VARCHAR(64)` | NOT NULL | ✓ (single) | No | SHA256 |
| `annual_income` | `DECIMAL(12,2)` | NOT NULL, CHECK > 0 | No | No | **Never log** |
| `employment_status` | `employment_status_enum` | NOT NULL | No | No | |
| `credit_score` | `INTEGER` | CHECK 300-900 | No | No | |
| `created_at` | `TIMESTAMP` | NOT NULL, default now() | No | No | Audit |
| `updated_at` | `TIMESTAMP` | NOT NULL, default now() | No | No | Audit |

**Indexes:**
- `idx_co_borrowers_application_id` ON (`application_id`)
- `idx_co_borrowers_sin_hash` ON (`sin_hash`)

**Relationships:**
- Many-to-One: `co_borrowers.application_id` → `applications.id` (CASCADE DELETE)

---

## 3. Business Logic

### Application Status Workflow
**State Machine:**
```
draft → submitted → underwriting → approved
   ↑        ↓             ↓            ↓
   └───── rejected ←─────┴───── withdrawn
```

**Transition Rules:**
- **draft → submitted**: Triggered by `POST /submit`. Validates GDS/TDS ≤ OSFI limits, CMHC insurance, and required fields.
- **submitted → underwriting**: Automatic transition after compliance checks pass. Sets `submitted_at`.
- **underwriting → approved/rejected**: Underwriter decision (via underwriting module).
- **Any → withdrawn**: Client/broker can withdraw before approval.

**Default Values:**
- `application_type`: `purchase` (most common)
- `mortgage_type`: `fixed`
- `interest_rate`: Retrieved from `common/config.py` `MARKET_BASE_RATE`
- `status`: `draft`

### Financial Validation Rules
| Field | Validation | Error Code | Regulatory Basis |
|-------|------------|------------|------------------|
| `purchase_price` | > 0 | `CLIENT_INTAKE_002` | Basic sanity |
| `down_payment` | ≥ 5% of purchase_price | `CLIENT_INTAKE_003` | CMHC minimum |
| `requested_loan_amount` | = purchase_price - down_payment | `CLIENT_INTAKE_002` | Internal consistency |
| `ltv_ratio` | ≤ 95% | `CLIENT_INTAKE_003` | CMHC maximum |
| `amortization_years` | 5-30 (if insurance_required), else 5-25 | `CLIENT_INTAKE_003` | CMHC/OSFI rules |
| `term_years` | 1-10 | `CLIENT_INTAKE_002` | Market standard |
| `annual_income` | > 0 | `CLIENT_INTAKE_002` | Basic sanity |

### CMHC Insurance Premium Calculation
**Trigger:** `IF (loan_amount / property_value) > 0.80 THEN insurance_required = TRUE`

**Premium Tiers (applied to loan_amount):**
- 80.01-85% LTV: 2.80%
- 85.01-90% LTV: 3.10%
- 90.01-95% LTV: 4.00%

**Formula:**
```python
insurance_premium = requested_loan_amount * premium_rate
```

**Implementation:** Calculated in `services.ApplicationService.calculate_insurance()` on create/update.

### OSFI B-20 GDS/TDS Pre-Check (on submit)
**Purpose:** Early validation before underwriting. Not final approval.

**Formulas:**
```
Gross Monthly Income = (client.annual_income + Σ co_borrower.annual_income) / 12
PITH = (Principal + Interest + Property Tax + Heating) estimate
GDS = PITH / Gross Monthly Income

Total Monthly Debt = PITH + other_debt_obligations (from credit module)
TDS = Total Monthly Debt / Gross Monthly Income

Qualifying Rate = max(contract_rate + 2%, 5.25%)
```

**Hard Limits:**
- GDS ≤ 39%
- TDS ≤ 44%

**Audit Logging:** Log calculation breakdown with `correlation_id` for OSFI audit.

### Co-Borrower Management
**Separate Endpoints:**
- `POST /api/v1/applications/{id}/co-borrowers` - Add co-borrower
- `DELETE /api/v1/applications/{id}/co-borrowers/{co_borrower_id}` - Remove (only in draft)

**Rules:**
- Maximum 3 co-borrowers per application
- SIN must be unique across active applications (check `sin_hash`)
- Income aggregated for GDS/TDS calculations

---

## 4. Migrations

### New Alembic Revision: `create_client_intake_tables`

**Operations:**

1. **Create Enum Types:**
   ```sql
   CREATE TYPE employment_status_enum AS ENUM ('employed', 'self_employed', 'unemployed', 'retired');
   CREATE TYPE marital_status_enum AS ENUM ('single', 'married', 'common_law', 'divorced', 'widowed');
   CREATE TYPE application_type_enum AS ENUM ('purchase', 'refinance', 'renewal');
   CREATE TYPE application_status_enum AS ENUM ('draft', 'submitted', 'underwriting', 'approved', 'rejected', 'withdrawn');
   CREATE TYPE property_type_enum AS ENUM ('single_family', 'condo', 'townhouse', 'multi_unit');
   CREATE TYPE mortgage_type_enum AS ENUM ('fixed', 'variable', 'adjustable');
   ```

2. **Create `clients` Table:**
   ```sql
   CREATE TABLE clients (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       user_id UUID NOT NULL REFERENCES users(id),
       sin_encrypted BYTEA NOT NULL,
       sin_hash VARCHAR(64) NOT NULL UNIQUE,
       date_of_birth_encrypted BYTEA NOT NULL,
       employment_status employment_status_enum NOT NULL,
       employer_name VARCHAR(255),
       years_employed DECIMAL(4,1) CHECK (years_employed >= 0),
       annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
       other_income DECIMAL(12,2) DEFAULT 0 CHECK (other_income >= 0),
       credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
       marital_status marital_status_enum NOT NULL,
       created_at TIMESTAMP NOT NULL DEFAULT NOW(),
       updated_at TIMESTAMP NOT NULL DEFAULT NOW()
   );
   CREATE INDEX idx_clients_user_id ON clients(user_id);
   CREATE INDEX idx_clients_sin_hash ON clients(sin_hash);
   CREATE INDEX idx_clients_created_at ON clients(created_at DESC);
   ```

3. **Create `applications` Table:**
   ```sql
   CREATE TABLE applications (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       client_id UUID NOT NULL REFERENCES clients(id),
       broker_id UUID REFERENCES users(id),
       application_type application_type_enum NOT NULL,
       status application_status_enum NOT NULL DEFAULT 'draft',
       property_address_encrypted TEXT NOT NULL,
       property_type property_type_enum NOT NULL,
       property_value DECIMAL(12,2) NOT NULL CHECK (property_value > 0),
       purchase_price DECIMAL(12,2) NOT NULL CHECK (purchase_price > 0),
       down_payment DECIMAL(12,2) NOT NULL CHECK (down_payment >= 0),
       requested_loan_amount DECIMAL(12,2) NOT NULL CHECK (requested_loan_amount > 0),
       amortization_years INTEGER NOT NULL CHECK (amortization_years BETWEEN 5 AND 30),
       term_years INTEGER NOT NULL CHECK (term_years BETWEEN 1 AND 10),
       mortgage_type mortgage_type_enum NOT NULL,
       interest_rate DECIMAL(5,3) NOT NULL CHECK (interest_rate > 0),
       created_at TIMESTAMP NOT NULL DEFAULT NOW(),
       updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
       submitted_at TIMESTAMP
   );
   CREATE INDEX idx_applications_client_id ON applications(client_id);
   CREATE INDEX idx_applications_broker_id ON applications(broker_id);
   CREATE INDEX idx_applications_status_created_at ON applications(status, created_at DESC);
   CREATE INDEX idx_applications_submitted_at ON applications(submitted_at) WHERE submitted_at IS NOT NULL;
   CREATE INDEX idx_applications_loan_amount ON applications(requested_loan_amount);
   ```

4. **Create `co_borrowers` Table:**
   ```sql
   CREATE TABLE co_borrowers (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
       full_name VARCHAR(255) NOT NULL,
       sin_encrypted BYTEA NOT NULL,
       sin_hash VARCHAR(64) NOT NULL,
       annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
       employment_status employment_status_enum NOT NULL,
       credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
       created_at TIMESTAMP NOT NULL DEFAULT NOW(),
       updated_at TIMESTAMP NOT NULL DEFAULT NOW()
   );
   CREATE INDEX idx_co_borrowers_application_id ON co_borrowers(application_id);
   CREATE INDEX idx_co_borrowers_sin_hash ON co_borrowers(sin_hash);
   ```

5. **Data Migration Needs:** None (new tables only)

---

## 5. Security & Compliance

### PIPEDA Compliance
- **Encryption at Rest:** All SIN/DOB fields use AES-256-GCM via `common/security.encrypt_pii()`. Encryption key from `settings.PII_ENCRYPTION_KEY` (32-byte, environment variable).
- **Data Minimization:** Only collect fields required for underwriting. No optional PII fields.
- **No Logging:** `structlog` configuration filters out `sin`, `date_of_birth`, `annual_income`, `other_income`, `requested_loan_amount` from logs.
- **Lookup Hashing:** `sin_hash` stored as SHA256 for duplicate checks without revealing SIN.

### OSFI B-20 Requirements
- **Stress Test:** On submit, calculate qualifying rate = `max(contract_rate + 2%, 5.25%)`.
- **GDS/TDS Limits:** Hard enforcement at submit: GDS ≤ 39%, TDS ≤ 44%. Log full calculation with `correlation_id`.
- **Auditable:** Store calculation breakdown in `application_logs` table (separate audit module) for 7-year retention.

### FINTRAC Requirements
- **Immutable Records:** Applications never deleted. `status = 'withdrawn'` for cancellations.
- **Transaction Reporting:** If `requested_loan_amount ≥ 10,000`, set `fintrac_reportable = true` and trigger `FINTRACReportService.create_large_transaction_record()`.
- **5-Year Retention:** All records retained via PostgreSQL `RETENTION POLICY` (administered by DBA).

### CMHC Insurance Logic
- **LTV Calculation:** `ltv = requested_loan_amount / property_value` (use Decimal, no rounding).
- **Premium Lookup:** Use tiered rates (2.80%, 3.10%, 4.00%) applied to loan amount.
- **Amortization Cap:** If `insurance_required = false`, enforce `amortization_years ≤ 25`.

### Access Control
- **Client Role:** Can only `GET/POST/PUT` applications where `client.user_id = auth.user_id`.
- **Broker Role:** Can only `GET/POST/PUT` applications where `application.broker_id = auth.user_id` or `broker_id IS NULL` (unassigned).
- **Admin Role:** Full access via separate admin module.

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `ApplicationNotFoundError` | 404 | `CLIENT_INTAKE_001` | "Application {id} not found" | GET /applications/{invalid_uuid} |
| `ApplicationValidationError` | 422 | `CLIENT_INTAKE_002` | "{field}: {reason}" | amortization_years = 35 |
| `ApplicationBusinessRuleError` | 409 | `CLIENT_INTAKE_003` | "{rule} violated: {detail}" | LTV > 95% |
| `ApplicationAccessDeniedError` | 403 | `CLIENT_INTAKE_004` | "Access denied to application {id}" | Client viewing another's app |
| `ApplicationStatusTransitionError` | 409 | `CLIENT_INTAKE_005` | "Invalid transition from {status} to {target}" | Submitting approved app |
| `CoBorrowerLimitExceededError` | 400 | `CLIENT_INTAKE_006` | "Maximum 3 co-borrowers allowed" | Adding 4th co-borrower |
| `DuplicateSINError` | 409 | `CLIENT_INTAKE_007` | "SIN already associated with active application" | Hash collision check |

**Structured Error Response Format:**
```json
{
  "detail": "Application business rule violated: LTV ratio 96.5% exceeds maximum 95%",
  "error_code": "CLIENT_INTAKE_003",
  "correlation_id": "a1b2c3d4-e5f6-7890",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

---

## Additional Considerations

### SIN Encryption Key Management
- **Strategy:** Use AWS KMS or HashiCorp Vault to manage `PII_ENCRYPTION_KEY`. Never commit to repo.
- **Rotation:** Implement key versioning in `common/security.py` with `key_id` stored alongside encrypted data.
- **Backup:** Key must be backed up to secure offline storage (regulatory requirement).

### Co-Borrower Management Endpoints
To be implemented in same module:
- `POST /api/v1/applications/{id}/co-borrowers` - Add co-borrower
- `DELETE /api/v1/applications/{id}/co-borrowers/{co_borrower_id}` - Remove (draft only)
- `PUT /api/v1/applications/{id}/co-borrowers/{co_borrower_id}` - Update co-borrower

### Default Application Types
- `purchase`: Primary residence purchase (default)
- `refinance`: Refinance existing mortgage
- `renewal`: Mortgage renewal at term end

### Default Mortgage Types
- `fixed`: Fixed interest rate for term
- `variable`: Variable rate, payment fixed
- `adjustable`: Adjustable rate, payment changes

### Observability
- **Metrics:** `applications_created_total`, `applications_submitted_total`, `gds_ratio_histogram`, `tds_ratio_histogram`
- **Tracing:** Span per compliance check, encrypt/decrypt operations
- **Logging:** Log status transitions, validation failures, access denied events (excluding PII)

---

**Document Version:** 1.0  
**Last Updated:** 2024-01-15  
**Author:** Designer Agent (Complexity: Reasoning)