# Client Intake & Application
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Client Intake & Application Module Design

**Design Document Location**: `docs/design/client-intake-application.md`  
**Module Identifier**: `client_intake`  
**Last Updated**: 2024

---

## 1. Endpoints

### `POST /api/v1/applications`
Create a new mortgage application (draft status). Supports creating a new client record or linking an existing client.

- **Authentication**: Required (JWT, roles: `client`, `broker`)
- **Authorization**: Clients can only create for themselves; brokers can create for assigned clients
- **Request Body** (`ApplicationCreate`):
  ```json
  {
    "client": {
      "user_id": "uuid",  // Optional: link existing user
      "sin_plain": "123-456-789",  // PIPEDA: encrypted at rest, never logged
      "date_of_birth_plain": "1985-06-15",  // PIPEDA: encrypted at rest
      "employment_status": "full_time",
      "employer_name": "Acme Corp",
      "years_employed": "3.5",  // Decimal
      "annual_income": "85000.00",  // Decimal > 0
      "other_income": "5000.00",  // Optional Decimal
      "credit_score": 720,  // Optional integer
      "marital_status": "married"
    },
    "property_address": {
      "street": "123 Main St",
      "city": "Toronto",
      "province": "ON",
      "postal_code": "M5V 3A8"
    },
    "property_type": "single_family",
    "property_value": "750000.00",  // Decimal > 0
    "purchase_price": "750000.00",  // Decimal > 0, must be > 0
    "down_payment": "75000.00",  // Decimal, minimum 5% validation
    "amortization_years": 25,  // Integer: 5-30 (insured) or 5-25 (uninsured)
    "term_years": 5,  // Integer: 1-10
    "mortgage_type": "fixed",  // Enum: fixed, variable, adjustable
    "application_type": "purchase",  // Enum: purchase, refinance, renewal
    "co_borrowers": [  // Optional
      {
        "full_name": "Jane Doe",
        "sin_plain": "987-654-321",
        "annual_income": "65000.00",
        "employment_status": "full_time",
        "credit_score": 710
      }
    ]
  }
  ```
- **Response** (`ApplicationDetail`, 201 Created):
  ```json
  {
    "id": "app_uuid",
    "client_id": "client_uuid",
    "broker_id": "broker_uuid",
    "status": "draft",
    "application_type": "purchase",
    "property_address": { ... },
    "property_type": "single_family",
    "property_value": "750000.00",
    "purchase_price": "750000.00",
    "down_payment": "75000.00",
    "requested_loan_amount": "675000.00",  // Calculated
    "ltv_ratio": "0.90",  // Calculated Decimal
    "insurance_required": true,  // CMHC: LTV > 80%
    "insurance_premium_amount": "20250.00",  // CMHC tier calculation
    "amortization_years": 25,
    "term_years": 5,
    "mortgage_type": "fixed",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z",
    "submitted_at": null,
    "co_borrowers": [
      {
        "id": "cb_uuid",
        "full_name": "Jane Doe",
        "annual_income": "65000.00",
        "employment_status": "full_time",
        "credit_score": 710
        // SIN never returned
      }
    ]
  }
  ```
- **Error Responses**:
  - `422` (`INTAKE_002`): Validation error (e.g., `purchase_price: must be greater than 0`)
  - `422` (`INTAKE_005`): Co-borrower validation error
  - `403` (`INTAKE_006`): Unauthorized to create application for this client
  - `409` (`INTAKE_003`): Client already has active application in draft/submitted state

---

### `GET /api/v1/applications`
List applications with pagination and filtering. Access controlled by role.

- **Authentication**: Required (JWT)
- **Authorization**: Clients see only own applications; brokers see only assigned; underwriters see all submitted
- **Query Parameters**:
  - `status`: Optional filter (e.g., `draft`, `submitted`)
  - `page`: Integer, default 1
  - `limit`: Integer, default 20, max 100
- **Response** (`ApplicationList`, 200 OK):
  ```json
  {
    "items": [
      {
        "id": "app_uuid",
        "status": "draft",
        "application_type": "purchase",
        "property_address": { "city": "Toronto", "province": "ON" },
        "purchase_price": "750000.00",
        "requested_loan_amount": "675000.00",
        "created_at": "2024-01-15T10:30:00Z",
        "submitted_at": null
      }
    ],
    "total": 1,
    "page": 1,
    "limit": 20
  }
  ```
- **Error Responses**:
  - `403` (`INTAKE_006`): Access denied to broker's unassigned applications

---

### `GET /api/v1/applications/{id}`
Retrieve a single application by ID. Full detail view.

- **Authentication**: Required (JWT)
- **Authorization**: Must be owner, assigned broker, or underwriter
- **Response** (`ApplicationDetail`, 200 OK): Same structure as POST response
- **Error Responses**:
  - `404` (`INTAKE_001`): Application not found
  - `403` (`INTAKE_006`): Access denied

---

### `PUT /api/v1/applications/{id}`
Update an existing application. Only allowed in `draft` or `returned` status.

- **Authentication**: Required (JWT)
- **Authorization**: Must be owner or assigned broker
- **Request Body** (`ApplicationUpdate`):
  ```json
  {
    "property_value": "760000.00",  // Partial updates allowed
    "down_payment": "80000.00",
    "co_borrowers": [  // Full replacement array
      {
        "id": "cb_uuid",  // Optional: include to update existing
        "full_name": "Jane Doe",
        "sin_plain": "987-654-321",
        "annual_income": "66000.00"
      }
    ]
  }
  ```
- **Response** (`ApplicationDetail`, 200 OK): Updated application
- **Error Responses**:
  - `404` (`INTAKE_001`): Application not found
  - `403` (`INTAKE_006`): Access denied
  - `409` (`INTAKE_003`): Invalid state transition (cannot edit in `submitted` status)
  - `422` (`INTAKE_002`): Validation error on updated fields

---

### `POST /api/v1/applications/{id}/submit`
Submit application for underwriting. Triggers validation, state machine transition, and FINTRAC logging.

- **Authentication**: Required (JWT)
- **Authorization**: Must be owner or assigned broker
- **Request Body**: Empty object `{}` or `{"confirm": true}`
- **Response** (`ApplicationDetail`, 200 OK):
  ```json
  {
    "id": "app_uuid",
    "status": "submitted",  // Transitioned from draft
    "submitted_at": "2024-01-15T11:00:00Z",
    // ... other fields
  }
  ```
- **Business Logic**:
  - Validates all required fields populated
  - Calculates LTV and CMHC insurance requirement
  - Generates FINTRAC record if `requested_loan_amount > 10000.00`
  - Logs identity verification event (client identity confirmed at submission)
  - Transitions status: `draft` → `submitted`
  - Creates audit trail entry
- **Error Responses**:
  - `404` (`INTAKE_001`): Application not found
  - `403` (`INTAKE_006`): Access denied
  - `409` (`INTAKE_003`): Business rule violation (e.g., LTV > 95%, income insufficient)
  - `422` (`INTAKE_002`): Missing required fields

---

### `GET /api/v1/applications/{id}/summary`
Generate PDF-ready JSON summary for document generation.

- **Authentication**: Required (JWT)
- **Authorization**: Must be owner, assigned broker, or underwriter
- **Response** (`ApplicationSummaryPDF`, 200 OK):
  ```json
  {
    "application_id": "app_uuid",
    "generated_at": "2024-01-15T11:00:00Z",
    "client": {
      "name": "John Doe",  // From user profile
      "employment_status": "full_time",
      "employer_name": "Acme Corp",
      "years_employed": "3.5",
      "annual_income": "85000.00",
      "other_income": "5000.00",
      "credit_score": 720
      // SIN and DOB excluded
    },
    "co_borrowers": [...],
    "property": { ... },
    "loan_details": {
      "purchase_price": "750000.00",
      "down_payment": "75000.00",
      "loan_amount": "675000.00",
      "ltv_ratio": "90.00%",
      "insurance_required": true,
      "insurance_premium": "20250.00",
      "amortization": "25 years",
      "term": "5 years",
      "mortgage_type": "fixed"
    },
    "regulatory_disclosures": {
      "fintrac_reported": true,
      "cmhc_insurance_eligible": true
    }
  }
  ```
- **Error Responses**:
  - `404` (`INTAKE_001`): Application not found
  - `403` (`INTAKE_006`): Access denied

---

## 2. Models & Database

### `clients` Table
```sql
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    sin_encrypted BYTEA NOT NULL,  -- PIPEDA: AES-256 encrypted
    sin_hash VARCHAR(64) NOT NULL,  -- SHA256 for lookups, PIPEDA compliant
    date_of_birth_encrypted BYTEA NOT NULL,  -- PIPEDA: AES-256 encrypted
    employment_status VARCHAR(50) NOT NULL CHECK (employment_status IN ('full_time', 'part_time', 'self_employed', 'unemployed', 'retired')),
    employer_name VARCHAR(255),
    years_employed NUMERIC(5,2),
    annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
    other_income DECIMAL(12,2) DEFAULT 0.00,
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    marital_status VARCHAR(50) CHECK (marital_status IN ('single', 'married', 'common_law', 'divorced', 'widowed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT unique_user_id UNIQUE (user_id),
    INDEX idx_clients_sin_hash (sin_hash),
    INDEX idx_clients_user_id (user_id)
);
```

### `applications` Table
```sql
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    broker_id UUID REFERENCES users(id) ON DELETE SET NULL,
    application_type VARCHAR(50) NOT NULL DEFAULT 'purchase' CHECK (application_type IN ('purchase', 'refinance', 'renewal')),
    status VARCHAR(50) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'underwriting', 'approved', 'rejected', 'conditions', 'closed')),
    property_address JSONB NOT NULL,  -- Structured: {street, city, province, postal_code}
    property_type VARCHAR(100) NOT NULL CHECK (property_type IN ('single_family', 'condo', 'townhouse', 'multi_unit', 'vacation_property')),
    property_value DECIMAL(12,2) NOT NULL CHECK (property_value > 0),
    purchase_price DECIMAL(12,2) NOT NULL CHECK (purchase_price > 0),
    down_payment DECIMAL(12,2) NOT NULL CHECK (down_payment > 0),
    requested_loan_amount DECIMAL(12,2) GENERATED ALWAYS AS (purchase_price - down_payment) STORED,
    ltv_ratio DECIMAL(5,4) GENERATED ALWAYS AS (requested_loan_amount / NULLIF(property_value, 0)) STORED,
    insurance_required BOOLEAN GENERATED ALWAYS AS (ltv_ratio > 0.80) STORED,
    insurance_premium_amount DECIMAL(12,2),  -- CMHC: calculated on submit
    amortization_years INTEGER NOT NULL CHECK (amortization_years BETWEEN 5 AND 30),
    term_years INTEGER NOT NULL CHECK (term_years BETWEEN 1 AND 10),
    mortgage_type VARCHAR(50) NOT NULL DEFAULT 'fixed' CHECK (mortgage_type IN ('fixed', 'variable', 'adjustable')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    created_by VARCHAR(100) NOT NULL,  -- FINTRAC: immutable audit trail
    
    -- Indexes
    INDEX idx_applications_client_id (client_id),
    INDEX idx_applications_broker_id (broker_id),
    INDEX idx_applications_status (status),
    INDEX idx_applications_submitted_at (submitted_at),
    INDEX idx_applications_created_at (created_at),
    INDEX idx_applications_ltv (ltv_ratio)
);

-- Trigger for updated_at
CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### `co_borrowers` Table
```sql
CREATE TABLE co_borrowers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    sin_encrypted BYTEA NOT NULL,  -- PIPEDA: AES-256 encrypted
    sin_hash VARCHAR(64) NOT NULL,
    annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
    employment_status VARCHAR(50) NOT NULL,
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_co_borrowers_application_id (application_id),
    INDEX idx_co_borrowers_sin_hash (sin_hash)
);
```

**Encryption Implementation**:
- Use `common/security.py::encrypt_pii()` and `decrypt_pii()` with AES-256-GCM
- Key management via environment variable `PII_ENCRYPTION_KEY` (32-byte base64)
- Production: Use AWS KMS or Azure Key Vault integration
- Key rotation: New key version encrypts new records; old key retained for decryption

---

## 3. Business Logic

### Application Status State Machine
```
draft → submitted → underwriting → approved → closed
          ↓                ↓               ↓
          └──→ rejected ←──┴──→ conditions
```

**Transition Rules**:
- `draft` → `submitted`: Client/broker action; triggers validation and FINTRAC check
- `submitted` → `underwriting`: Automated on successful validation; assigns to underwriter
- `underwriting` → `approved`/`rejected`/`conditions`: Underwriter decision
- `conditions` → `approved`: Conditions met verification
- `approved` → `closed`: Funding completed (external event)

### Validation Algorithm (on submit)
```python
# Pseudocode for services.py::validate_and_submit()
async def validate_application(app: Application):
    # 1. Basic field validation
    assert app.purchase_price > 0, "purchase_price must be > 0"
    assert app.annual_income > 0, "income must be > 0"
    
    # 2. CMHC eligibility (uninsured constraints)
    if not app.insurance_required:
        assert app.amortization_years <= 25, "Uninsured max amortization 25 years"
    
    # 3. Down payment minimums
    min_down = app.purchase_price * Decimal('0.05')
    assert app.down_payment >= min_down, "Down payment < 5%"
    
    # 4. LTV validation (CMHC max 95%)
    assert app.ltv_ratio <= Decimal('0.95'), "LTV exceeds 95% maximum"
    
    # 5. FINTRAC: Large transaction flag
    if app.requested_loan_amount > Decimal('10000.00'):
        await fintrac_service.log_large_transaction(app)
    
    # 6. Identity verification audit (FINTRAC)
    await audit_service.log_identity_verification(
        client_id=app.client_id,
        verified_by=current_user.id,
        method="document_verification"
    )
    
    # 7. State transition
    app.status = "submitted"
    app.submitted_at = datetime.utcnow()
```

### CMHC Insurance Premium Calculation
```python
def calculate_cmhc_premium(loan_amount: Decimal, ltv: Decimal) -> Decimal:
    """
    CMHC premium tiers:
    - 80.01-85%: 2.80%
    - 85.01-90%: 3.10%
    - 90.01-95%: 4.00%
    """
    if ltv <= Decimal('0.80'):
        return Decimal('0.00')
    elif ltv <= Decimal('0.85'):
        rate = Decimal('0.0280')
    elif ltv <= Decimal('0.90'):
        rate = Decimal('0.0310')
    elif ltv <= Decimal('0.95'):
        rate = Decimal('0.0400')
    else:
        raise ValueError("LTV exceeds CMHC maximum")
    
    premium = loan_amount * rate
    return premium.quantize(Decimal('0.01'))
```

### Co-Borrower Management
- **Addition**: Include in `POST` or `PUT` request; full array replacement on update
- **Removal**: Submit `PUT` with empty array `[]` or omitted co_borrowers field
- **Update**: Include `id` in co_borrower object to update existing record
- **Constraint**: Maximum 3 co-borrowers per application (business rule)

---

## 4. Migrations

### Alembic Migration: `001_create_client_intake_tables.py`

```python
# New Tables
create_table('clients', ...)
create_table('applications', ...)
create_table('co_borrowers', ...)

# Indexes
op.create_index('idx_clients_sin_hash', 'clients', ['sin_hash'])
op.create_index('idx_applications_client_id', 'applications', ['client_id'])
op.create_index('idx_applications_broker_status', 'applications', ['broker_id', 'status'])
op.create_index('idx_co_borrowers_app_id', 'co_borrowers', ['application_id'])

# Generated columns and triggers already defined in SQLAlchemy models
```

### Data Migration Needs
- **None**: This is a new module; no existing data to migrate
- **Future**: If migrating from legacy system, map SIN to encrypted fields using bulk encryption script

---

## 5. Security & Compliance

### OSFI B-20 Requirements
- **Data Preparation**: Module captures all income, property value, and liability data required for GDS/TDS calculations
- **Audit Logging**: All financial inputs logged (income, property_value, purchase_price) with correlation_id for underwriting audit trail
- **Stress Test Readiness**: Store `contract_rate` and `qualifying_rate` in related `underwriting` module; intake module provides baseline data

### FINTRAC Compliance
- **Immutable Audit Trail**: All tables have `created_at` and `created_by` (populated from JWT `sub` claim)
- **Large Transaction Flagging**: Automatic flagging when `requested_loan_amount > CAD $10,000`; logs to `fintrac_reports` table
- **Identity Verification**: `POST /submit` logs verification event with method, timestamp, and user ID
- **5-Year Retention**: PostgreSQL `RETENTION POLICY` on tables (soft delete via `archived_at` flag; physical deletion prohibited)
- **No Deletion**: Applications cannot be deleted; only archived after 5 years

### CMHC Insurance Logic
- **LTV Calculation**: Use `DECIMAL(5,4)` with no precision loss: `ltv_ratio = requested_loan_amount / property_value`
- **Insurance Required**: Generated column `insurance_required = ltv_ratio > 0.80`
- **Premium Calculation**: On submit, calculate and store `insurance_premium_amount` using tier lookup
- **Tier Boundaries**: Strictly enforce inclusive/exclusive bounds (e.g., 85.01% triggers 3.10% rate)

### PIPEDA Data Handling
- **Encryption at Rest**: `sin_encrypted` and `date_of_birth_encrypted` use AES-256-GCM via `common/security.py`
- **No Logging**: `encrypt_pii()` and `decrypt_pii()` mask values in logs; structlog filters exclude these fields
- **Lookup Hashing**: `sin_hash` = SHA256(SIN) for duplicate checks; hash cannot be reversed
- **Data Minimization**: Only collect fields required for underwriting decision; `other_income` and `credit_score` are optional
- **API Response Filtering**: Pydantic schemas exclude all encrypted fields; `sin_plain` and `date_of_birth_plain` are write-only

### Authentication & Authorization
- **JWT Claims**: `sub` (user ID), `role` (client, broker, underwriter, admin), `broker_id` (if applicable)
- **Access Control Matrix**:
  | Endpoint | Client | Broker | Underwriter |
  |----------|--------|--------|-------------|
  | POST /applications | Own only | Assigned only | No |
  | GET /applications | Own only | Assigned only | All submitted |
  | GET /{id} | Own only | Assigned only | All submitted |
  | PUT /{id} | Own draft only | Assigned draft only | No |
  | POST /{id}/submit | Own draft only | Assigned draft only | No |
  | GET /{id}/summary | Own only | Assigned only | All submitted |

---

## 6. Error Codes & HTTP Responses

All exceptions inherit from `common.exceptions.AppException` and are defined in `modules/client_intake/exceptions.py`.

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `ApplicationNotFoundError` | 404 | `INTAKE_001` | "Application {id} not found" | GET non-existent UUID |
| `ApplicationValidationError` | 422 | `INTAKE_002` | "{field}: {reason}" | purchase_price = 0 |
| `ApplicationStateError` | 409 | `INTAKE_003` | "Invalid state transition from {current} to {target}" | Submit already submitted app |
| `ClientNotFoundError` | 404 | `INTAKE_004` | "Client {id} not found" | Referenced client doesn't exist |
| `CoBorrowerValidationError` | 422 | `INTAKE_005` | "Co-borrower {index}.{field}: {reason}" | Co-borrower income = 0 |
| `UnauthorizedAccessError` | 403 | `INTAKE_006` | "Access denied to application {id}" | Broker accessing unassigned app |
| `SINDuplicateError` | 409 | `INTAKE_007` | "SIN already exists for client" | Hash collision on create |
| `FINTRACLoggingError` | 500 | `INTAKE_008` | "Failed to create FINTRAC audit record" | Database failure on submit |

### Error Response Format
```json
{
  "detail": "purchase_price: must be greater than 0",
  "error_code": "INTAKE_002",
  "correlation_id": "req-uuid",
  "timestamp": "2024-01-15T11:00:00Z"
}
```

**Logging**: All errors logged with `structlog` at WARNING/ERROR level; SIN/DOB/income values explicitly excluded from log context.