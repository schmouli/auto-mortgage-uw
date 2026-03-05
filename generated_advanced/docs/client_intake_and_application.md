# Client Intake & Application
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Client Intake & Application Module Design

**Module ID:** `INTAKE`  
**Feature Slug:** `client-intake-application`  
**File:** `docs/design/client-intake-application.md`

---

## 1. Endpoints

### `POST /api/v1/applications`
Create a new mortgage application (draft status).

**Authentication:** Authenticated (client or broker)

**Request Body (`CreateApplicationRequest`):**
```json
{
  "client": {
    "sin": "string", // 9 digits, encrypted before storage
    "date_of_birth": "date", // ISO 8601, encrypted before storage
    "employment_status": "enum",
    "employer_name": "string",
    "years_employed": "decimal",
    "annual_income": "decimal",
    "other_income": "decimal|null",
    "credit_score": "integer|null",
    "marital_status": "enum|null"
  },
  "property_address": {
    "street": "string",
    "city": "string",
    "province": "string",
    "postal_code": "string"
  },
  "property_type": "enum",
  "property_value": "decimal",
  "purchase_price": "decimal|null",
  "down_payment": "decimal|null",
  "requested_loan_amount": "decimal",
  "amortization_years": "integer",
  "term_years": "integer",
  "mortgage_type": "enum",
  "application_type": "enum",
  "co_borrowers": [
    {
      "full_name": "string",
      "sin": "string",
      "annual_income": "decimal",
      "employment_status": "enum",
      "credit_score": "integer|null"
    }
  ]
}
```

**Response (`ApplicationResponse`) 201:**
```json
{
  "id": "uuid",
  "client_id": "uuid",
  "broker_id": "uuid|null",
  "status": "draft",
  "application_type": "enum",
  "property_address": { "street": "string", "city": "string", "province": "string", "postal_code": "string" },
  "property_type": "enum",
  "property_value": "decimal",
  "purchase_price": "decimal|null",
  "down_payment": "decimal|null",
  "requested_loan_amount": "decimal",
  "amortization_years": "integer",
  "term_years": "integer",
  "mortgage_type": "enum",
  "ltv_ratio": "decimal|null",
  "insurance_required": "boolean|null",
  "insurance_premium": "decimal|null",
  "created_at": "datetime",
  "updated_at": "datetime",
  "submitted_at": "datetime|null",
  "co_borrowers": [
    {
      "id": "uuid",
      "full_name": "string",
      "annual_income": "decimal",
      "employment_status": "enum",
      "credit_score": "integer|null"
    }
  ]
}
```

**Error Responses:**
| HTTP | Error Code | Detail |
|------|------------|--------|
| 422 | `INTAKE_002` | `{field}: validation error detail` |
| 403 | `INTAKE_004` | "Insufficient permissions to create application" |
| 409 | `INTAKE_003` | "LTV exceeds maximum for uninsured mortgage" |

---

### `GET /api/v1/applications`
List applications with pagination and filtering.

**Authentication:** Authenticated (client sees own; broker sees assigned)

**Query Parameters:**
- `status`: string (optional, filter by status)
- `page`: integer (default: 1)
- `limit`: integer (default: 20, max: 100)

**Response (`PaginatedApplicationList`) 200:**
```json
{
  "items": [ /* ApplicationResponse objects */ ],
  "total": "integer",
  "page": "integer",
  "limit": "integer"
}
```

**Error Responses:**
| HTTP | Error Code | Detail |
|------|------------|--------|
| 403 | `INTAKE_004` | "Access denied to requested resource scope" |

---

### `GET /api/v1/applications/{id}`
Get single application details.

**Authentication:** Authenticated (client=own only; broker=assigned only; admin=any)

**Response (`ApplicationResponse`) 200:** Same as POST response

**Error Responses:**
| HTTP | Error Code | Detail |
|------|------------|--------|
| 404 | `INTAKE_001` | "Application not found" |
| 403 | `INTAKE_004` | "Access denied to application" |

---

### `PUT /api/v1/applications/{id}`
Update application (draft status only).

**Authentication:** Authenticated (owner only)

**Request Body (`UpdateApplicationRequest`):**
Same as `CreateApplicationRequest` but all fields optional. Partial updates supported.

**Response (`ApplicationResponse`) 200:** Updated application

**Error Responses:**
| HTTP | Error Code | Detail |
|------|------------|--------|
| 404 | `INTAKE_001` | "Application not found" |
| 403 | `INTAKE_004` | "Only application owner can update" |
| 409 | `INTAKE_005` | "Cannot modify submitted application" |
| 422 | `INTAKE_002` | Validation error |

---

### `POST /api/v1/applications/{id}/submit`
Submit application for underwriting.

**Authentication:** Authenticated (owner only)

**Request Body:** Empty or `SubmitApplicationRequest` with optional `declared_occupancy_type`.

**Response (`ApplicationSubmittedResponse`) 202:**
```json
{
  "id": "uuid",
  "status": "submitted",
  "submitted_at": "datetime",
  "next_steps": "string",
  "gds_calculation": {
    "gross_monthly_income": "decimal",
    "pith_amount": "decimal",
    "gds_ratio": "decimal",
    "qualifying_rate": "decimal",
    "passes_osfi_limit": "boolean"
  },
  "tds_calculation": {
    "other_debt_payments": "decimal",
    "tds_ratio": "decimal",
    "passes_osfi_limit": "boolean"
  }
}
```

**Error Responses:**
| HTTP | Error Code | Detail |
|------|------------|--------|
| 404 | `INTAKE_001` | "Application not found" |
| 403 | `INTAKE_004` | "Only owner can submit" |
| 422 | `INTAKE_002` | "Missing required fields: {list}" |
| 409 | `INTAKE_003` | "GDS/TDS exceeds OSFI B-20 limits" |
| 409 | `INTAKE_005` | "Application already submitted" |

---

### `GET /api/v1/applications/{id}/summary`
Get PDF-ready JSON summary for document generation.

**Authentication:** Authenticated (owner or assigned broker)

**Response (`ApplicationSummaryResponse`) 200:**
```json
{
  "application_id": "uuid",
  "generated_at": "datetime",
  "client": {
    "name": "string",
    "employment_status": "enum",
    "employer_name": "string",
    "years_employed": "decimal",
    "annual_income": "decimal",
    "other_income": "decimal|null",
    "credit_score": "integer|null",
    "marital_status": "enum|null"
  },
  "property": {
    "address": { "street": "string", "city": "string", "province": "string", "postal_code": "string" },
    "type": "enum",
    "value": "decimal",
    "purchase_price": "decimal|null"
  },
  "mortgage_details": {
    "loan_amount": "decimal",
    "down_payment": "decimal|null",
    "amortization_years": "integer",
    "term_years": "integer",
    "mortgage_type": "enum",
    "ltv_ratio": "decimal",
    "insurance_required": "boolean",
    "insurance_premium": "decimal|null"
  },
  "co_borrowers": [
    {
      "full_name": "string",
      "annual_income": "decimal",
      "employment_status": "enum",
      "credit_score": "integer|null"
    }
  ],
  "compliance_flags": {
    "fintrac_reportable": "boolean",
    "osfi_gds_ratio": "decimal",
    "osfi_tds_ratio": "decimal",
    "cmhc_insurance_tier": "string|null"
  }
}
```

**Error Responses:**
| HTTP | Error Code | Detail |
|------|------------|--------|
| 404 | `INTAKE_001` | "Application not found" |
| 403 | `INTAKE_004` | "Access denied" |

---

### Co-Borrower Management Endpoints

**`POST /api/v1/applications/{id}/co-borrowers`**
- Add co-borrower to draft application
- Request: `CoBorrowerCreate` (same as nested object above)
- Response: `CoBorrowerResponse` 201
- Errors: 404, 403, 409 (if submitted), 422

**`DELETE /api/v1/applications/{id}/co-borrowers/{co_borrower_id}`**
- Remove co-borrower from draft application
- Response: 204 No Content
- Errors: 404, 403, 409 (if submitted)

---

## 2. Models & Database

### Enum Types (PostgreSQL)
```sql
CREATE TYPE employment_status AS ENUM ('employed', 'self_employed', 'unemployed', 'retired');
CREATE TYPE marital_status AS ENUM ('single', 'married', 'common_law', 'divorced', 'widowed');
CREATE TYPE application_type AS ENUM ('purchase', 'refinance', 'renewal', 'transfer');
CREATE TYPE application_status AS ENUM ('draft', 'submitted', 'underwriting', 'approved', 'rejected', 'closed', 'funded');
CREATE TYPE property_type AS ENUM ('single_family', 'condo', 'townhouse', 'duplex', 'triplex', 'fourplex', 'vacant_land');
CREATE TYPE mortgage_type AS ENUM ('fixed', 'variable');
```

### Table: `clients`
```sql
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    sin_encrypted BYTEA NOT NULL, -- AES-256-GCM encrypted
    sin_hash VARCHAR(64) NOT NULL, -- SHA256(sin) for dedupe/lookup
    date_of_birth_encrypted BYTEA NOT NULL, -- AES-256-GCM encrypted
    employment_status employment_status NOT NULL,
    employer_name VARCHAR(255),
    years_employed DECIMAL(4,2), -- e.g., 5.50 years
    annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
    other_income DECIMAL(12,2),
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    marital_status marital_status,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT idx_clients_user_id UNIQUE (user_id),
    CONSTRAINT idx_clients_sin_hash UNIQUE (sin_hash)
);

CREATE INDEX idx_clients_created_at ON clients(created_at);
```

### Table: `applications`
```sql
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    broker_id UUID REFERENCES brokers(id) ON DELETE SET NULL,
    application_type application_type NOT NULL,
    status application_status NOT NULL DEFAULT 'draft',
    property_address JSONB NOT NULL, -- {street, city, province, postal_code}
    property_type property_type NOT NULL,
    property_value DECIMAL(12,2) NOT NULL CHECK (property_value > 0),
    purchase_price DECIMAL(12,2), -- NULL for refinance/renewal
    down_payment DECIMAL(12,2),
    requested_loan_amount DECIMAL(12,2) NOT NULL CHECK (requested_loan_amount > 0),
    amortization_years INTEGER NOT NULL CHECK (amortization_years BETWEEN 5 AND 30),
    term_years INTEGER NOT NULL CHECK (term_years BETWEEN 1 AND 10),
    mortgage_type mortgage_type NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    
    -- Compliance flags (calculated on submit)
    ltv_ratio DECIMAL(5,4),
    insurance_required BOOLEAN,
    insurance_premium DECIMAL(12,2),
    fintrac_reportable BOOLEAN GENERATED ALWAYS AS (requested_loan_amount >= 10000) STORED,
    
    -- Indexes
    CONSTRAINT idx_applications_client_id_status ON applications(client_id, status),
    CONSTRAINT idx_applications_broker_id ON applications(broker_id),
    CONSTRAINT idx_applications_status ON applications(status),
    CONSTRAINT idx_applications_submitted_at ON applications(submitted_at)
);

CREATE TRIGGER update_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### Table: `co_borrowers`
```sql
CREATE TABLE co_borrowers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    sin_encrypted BYTEA NOT NULL, -- AES-256-GCM encrypted
    sin_hash VARCHAR(64) NOT NULL, -- SHA256(sin) for lookup
    annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
    employment_status employment_status NOT NULL,
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT idx_co_borrowers_application_id ON co_borrowers(application_id),
    CONSTRAINT idx_co_borrowers_sin_hash UNIQUE (sin_hash)
);
```

### Relationships
- `clients` → `applications`: One-to-Many (client can have multiple applications)
- `applications` → `co_borrowers`: One-to-Many (application can have multiple co-borrowers)
- `applications` → `brokers`: Many-to-One (broker can have multiple applications)

---

## 3. Business Logic

### Validation Rules Engine
```python
# Executed on create/update and re-validated on submit
validate_application(app: Application) -> None:
    # Financial validations
    assert app.purchase_price > 0, "INTAKE_002: purchase_price must be positive"
    assert app.annual_income > 0, "INTAKE_002: annual_income must be positive"
    assert 1 <= app.term_years <= 10, "INTAKE_002: term_years out of range"
    
    # CMHC amortization limits
    ltv = app.requested_loan_amount / app.property_value
    if ltv > 0.80:
        assert 5 <= app.amortization_years <= 25, "INTAKE_003: Insured mortgages max 25 years"
    else:
        assert 5 <= app.amortization_years <= 30, "INTAKE_002: amortization_years out of range"
    
    # LTV ceiling check (OSFI)
    assert ltv <= 0.95, "INTAKE_003: LTV exceeds 95% maximum"
```

### Application State Machine
```
draft → submitted → underwriting → approved → funded → closed
           ↓                ↓              ↓
        rejected       rejected       rejected
```

**Transition Rules:**
- `draft` → `submitted`: Owner only; triggers validation + GDS/TDS calculation
- `submitted` → `underwriting`: Automatic on successful submit
- `underwriting` → `approved`: Underwriter only; GDS/TDS ≤ limits, LTV compliant
- `underwriting` → `rejected`: Underwriter only; with reason code
- `approved` → `funded`: Funding system trigger
- `funded` → `closed`: Post-funding completion

### GDS/TDS Calculation (OSFI B-20)
```python
calculate_debt_service_ratios(app: Application) -> Dict:
    # 1. Determine qualifying rate
    contract_rate = get_contract_rate(app.mortgage_type, app.term_years)
    qualifying_rate = max(contract_rate + 2.0, 5.25)
    
    # 2. Calculate monthly income (including co-borrowers)
    gross_monthly_income = (app.client.annual_income + 
                           sum(cb.annual_income for cb in app.co_borrowers)) / 12
    
    # 3. Calculate PITH (Principal, Interest, Taxes, Heating)
    monthly_payment = calculate_mortgage_payment(
        app.requested_loan_amount, 
        qualifying_rate, 
        app.amortization_years
    )
    property_tax = app.property_value * 0.01 / 12  # Estimated 1% annually
    heating = 150.00  # Standard estimate
    pith = monthly_payment + property_tax + heating
    
    # 4. GDS = PITH / Gross Monthly Income
    gds_ratio = pith / gross_monthly_income
    
    # 5. TDS = (PITH + Other Debt) / Gross Monthly Income
    other_debt = get_reported_debt_payments(app.client.id)  # From credit bureau integration
    tds_ratio = (pith + other_debt) / gross_monthly_income
    
    # 6. Audit logging (structlog)
    logger.info("debt_service_calculated",
                correlation_id=correlation_id,
                application_id=app.id,
                gds_ratio=gds_ratio,
                tds_ratio=tds_ratio,
                qualifying_rate=qualifying_rate,
                gross_monthly_income=gross_monthly_income,
                pith_breakdown={"payment": monthly_payment, "tax": property_tax, "heating": heating})
    
    # 7. OSFI limits enforcement
    if gds_ratio > 0.39:
        raise IntakeBusinessRuleError("GDS ratio exceeds 39% OSFI limit")
    if tds_ratio > 0.44:
        raise IntakeBusinessRuleError("TDS ratio exceeds 44% OSFI limit")
    
    return {"gds": gds_ratio, "tds": tds_ratio, "qualifying_rate": qualifying_rate}
```

### CMHC Insurance Calculation
```python
calculate_cmhc_insurance(app: Application) -> Tuple[bool, Decimal]:
    ltv = app.requested_loan_amount / app.property_value
    
    if ltv <= 0.80:
        return (False, Decimal('0.00'))
    
    # Premium tiers
    if 0.8001 <= ltv <= 0.85:
        premium_rate = Decimal('0.0280')
    elif 0.8501 <= ltv <= 0.90:
        premium_rate = Decimal('0.0310')
    elif 0.9001 <= ltv <= 0.95:
        premium_rate = Decimal('0.0400')
    else:
        raise IntakeBusinessRuleError("LTV exceeds insurable maximum")
    
    premium = app.requested_loan_amount * premium_rate
    return (True, premium.quantize(Decimal('0.01')))
```

### Co-Borrower Management Process
- **Addition**: Allowed only in `draft` status. Triggers income recalculation.
- **Removal**: Allowed only in `draft` status. Cascade delete.
- **Update**: Use PUT on co-borrower resource. Re-validates application.

---

## 4. Migrations

### Alembic Migration: `001_create_intake_tables.py`
```python
def upgrade():
    # Create enum types
    op.execute("CREATE TYPE employment_status AS ENUM ('employed', 'self_employed', 'unemployed', 'retired')")
    op.execute("CREATE TYPE marital_status AS ENUM ('single', 'married', 'common_law', 'divorced', 'widowed')")
    op.execute("CREATE TYPE application_type AS ENUM ('purchase', 'refinance', 'renewal', 'transfer')")
    op.execute("CREATE TYPE application_status AS ENUM ('draft', 'submitted', 'underwriting', 'approved', 'rejected', 'closed', 'funded')")
    op.execute("CREATE TYPE property_type AS ENUM ('single_family', 'condo', 'townhouse', 'duplex', 'triplex', 'fourplex', 'vacant_land')")
    op.execute("CREATE TYPE mortgage_type AS ENUM ('fixed', 'variable')")
    
    # Create clients table
    op.create_table('clients',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('sin_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('sin_hash', sa.String(64), nullable=False),
        sa.Column('date_of_birth_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('employment_status', sa.Enum('employed', 'self_employed', 'unemployed', 'retired', name='employment_status'), nullable=False),
        sa.Column('employer_name', sa.String(255), nullable=True),
        sa.Column('years_employed', sa.DECIMAL(precision=4, scale=2), nullable=True),
        sa.Column('annual_income', sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column('other_income', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('credit_score', sa.Integer(), nullable=True),
        sa.Column('marital_status', sa.Enum('single', 'married', 'common_law', 'divorced', 'widowed', name='marital_status'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
        sa.UniqueConstraint('sin_hash')
    )
    op.create_index('idx_clients_created_at', 'clients', ['created_at'])
    
    # Create applications table
    op.create_table('applications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('broker_id', sa.UUID(), nullable=True),
        sa.Column('application_type', sa.Enum('purchase', 'refinance', 'renewal', 'transfer', name='application_type'), nullable=False),
        sa.Column('status', sa.Enum('draft', 'submitted', 'underwriting', 'approved', 'rejected', 'closed', 'funded', name='application_status'), nullable=False),
        sa.Column('property_address', sa.JSONB(), nullable=False),
        sa.Column('property_type', sa.Enum('single_family', 'condo', 'townhouse', 'duplex', 'triplex', 'fourplex', 'vacant_land', name='property_type'), nullable=False),
        sa.Column('property_value', sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column('purchase_price', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('down_payment', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('requested_loan_amount', sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column('amortization_years', sa.Integer(), nullable=False),
        sa.Column('term_years', sa.Integer(), nullable=False),
        sa.Column('mortgage_type', sa.Enum('fixed', 'variable', name='mortgage_type'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ltv_ratio', sa.DECIMAL(precision=5, scale=4), nullable=True),
        sa.Column('insurance_required', sa.Boolean(), nullable=True),
        sa.Column('insurance_premium', sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column('fintrac_reportable', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_applications_client_id_status', 'applications', ['client_id', 'status'])
    op.create_index('idx_applications_broker_id', 'applications', ['broker_id'])
    op.create_index('idx_applications_status', 'applications', ['status'])
    op.create_index('idx_applications_submitted_at', 'applications', ['submitted_at'])
    
    # Create co_borrowers table
    op.create_table('co_borrowers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('sin_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('sin_hash', sa.String(64), nullable=False),
        sa.Column('annual_income', sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column('employment_status', sa.Enum('employed', 'self_employed', 'unemployed', 'retired', name='employment_status'), nullable=False),
        sa.Column('credit_score', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sin_hash')
    )
    op.create_index('idx_co_borrowers_application_id', 'co_borrowers', ['application_id'])
    
    # Create updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Apply trigger to applications table
    op.execute("""
        CREATE TRIGGER update_applications_updated_at
            BEFORE UPDATE ON applications
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
```

---

## 5. Security & Compliance

### PIPEDA - Data Encryption & Minimization
- **SIN Encryption**: AES-256-GCM with 12-byte nonce. Key managed via `common/security.py::encrypt_pii()` using AWS KMS envelope encryption. Never log plaintext SIN.
- **DOB Encryption**: Same AES-256-GCM scheme. Used only for age verification, never returned in APIs.
- **Lookup Strategy**: SHA256 hash of SIN stored in `sin_hash` column for duplicate detection and FINTRAC reporting. Hash salt = `config.PII_HASH_SALT`.
- **Data Minimization**: Only collect fields required for underwriting. `other_income` and `marital_status` are optional.

### OSFI B-20 - Debt Service Ratios
- **Stress Test**: Qualifying rate = `max(contract_rate + 2%, 5.25%)` enforced on submit.
- **Hard Limits**: GDS ≤ 39%, TDS ≤ 44%. Calculation logged with correlation_id for audit.
- **Audit Log Format**: 
```json
{
  "event": "debt_service_calculated",
  "correlation_id": "uuid",
  "application_id": "uuid",
  "gds_ratio": 0.38,
  "tds_ratio": 0.42,
  "qualifying_rate": 0.0725,
  "calculation_breakdown": {...}
}
```

### FINTRAC - Transaction Reporting
- **Threshold Flag**: `fintrac_reportable` boolean automatically set when `requested_loan_amount >= CAD $10,000`.
- **Immutable Records**: `created_at`, `submitted_at` timestamps never modified. No DELETE operations; use `closed` status for cancellations.
- **5-Year Retention**: All records retained per regulatory requirement. Implemented via soft-delete policy in data retention service.

### CMHC - Insurance Requirements
- **LTV Calculation**: `loan_amount / property_value` using Decimal with 4 decimal precision.
- **Insurance Trigger**: Automatically calculated on submit if LTV > 80%.
- **Premium Tiers**:
  - 80.01-85.00% → 2.80%
  - 85.01-90.00% → 3.10%
  - 90.01-95.00% → 4.00%
- **Premium Added**: To loan amount if insurance_required=True.

### Authorization Matrix
| Role | Create | Read Own | Read Assigned | Update | Submit | Delete |
|------|--------|----------|---------------|--------|--------|--------|
| Client | ✓ | ✓ | ✗ | ✓ (draft) | ✓ (own) | ✗ |
| Broker | ✓ | ✗ | ✓ | ✓ (draft) | ✓ (assigned) | ✗ |
| Admin | ✓ | ✓ (all) | ✓ (all) | ✓ (all) | ✓ (all) | ✗ (soft-close) |

---

## 6. Error Codes & HTTP Responses

### Exception Classes
```python
# modules/intake/exceptions.py
class IntakeNotFoundError(AppException):
    """Resource not found"""
    http_status = 404
    error_code = "INTAKE_001"
    message_template = "{resource_type} with id {resource_id} not found"

class IntakeValidationError(AppException):
    """Input validation failure"""
    http_status = 422
    error_code = "INTAKE_002"
    message_template = "{field}: {reason}"

class IntakeBusinessRuleError(AppException):
    """Business rule violation (OSFI, CMHC, etc.)"""
    http_status = 409
    error_code = "INTAKE_003"
    message_template = "Business rule violated: {rule_name} - {detail}"

class IntakePermissionError(AppException):
    """Authorization failure"""
    http_status = 403
    error_code = "INTAKE_004"
    message_template = "Access denied to {resource}"

class IntakeStateError(AppException):
    """Invalid state transition"""
    http_status = 409
    error_code = "INTAKE_005"
    message_template = "Invalid operation for status {current_status}"
```

### Error Response Format
All errors return consistent JSON:
```json
{
  "detail": "Human-readable message",
  "error_code": "INTAKE_00X",
  "correlation_id": "uuid",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### Edge Cases & Special Handling
- **Duplicate SIN**: On client creation, if `sin_hash` exists, return `INTAKE_002` with "Client already exists. Use existing client record."
- **LTV > 95%**: Reject with `INTAKE_003` "LTV exceeds maximum allowable for Canadian mortgages."
- **Submitted Application Edit**: Return `INTAKE_005` "Cannot modify submitted application. Contact underwriter."
- **Missing Co-Borrower SIN**: If co-borrower provided but SIN missing, `INTAKE_002` "Co-borrower SIN required for income verification."

---

## 7. SIN Encryption Key Management Strategy

### Recommended Implementation
```python
# common/security.py
class EncryptionService:
    def __init__(self):
        self.kms_client = boto3.client('kms')
        self.data_key_cache = TTLCache(maxsize=100, ttl=3600)
    
    def encrypt_pii(self, plaintext: str) -> bytes:
        # Envelope encryption: KMS data key + AES-256-GCM
        if not plaintext:
            return b''
        
        # Get data key from KMS
        data_key = self._get_data_key()
        aes_key = data_key['Plaintext']
        
        # Encrypt with AES-256-GCM
        nonce = os.urandom(12)
        cipher = Cipher(algorithms.AES(aes_key), modes.GCM(nonce))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext.encode()) + encryptor.finalize()
        
        # Store: nonce + ciphertext + tag
        return nonce + ciphertext + encryptor.tag
    
    def decrypt_pii(self, ciphertext: bytes) -> str:
        if not ciphertext:
            return ''
        
        # Extract components
        nonce = ciphertext[:12]
        tag = ciphertext[-16:]
        ciphertext = ciphertext[12:-16]
        
        # Decrypt data key from KMS
        data_key = self._get_data_key()
        aes_key = data_key['Plaintext']
        
        # Decrypt payload
        cipher = Cipher(algorithms.AES(aes_key), modes.GCM(nonce, tag))
        decryptor = cipher.decryptor()
        return (decryptor.update(ciphertext) + decryptor.finalize()).decode()
    
    def _get_data_key(self):
        # Cache KMS data key to reduce API calls
        cache_key = 'kms_data_key_intake'
        if cache_key not in self.data_key_cache:
            self.data_key_cache[cache_key] = self.kms_client.generate_data_key(
                KeyId=config.KMS_MASTER_KEY_ID,
                KeySpec='AES_256'
            )
        return self.data_key_cache[cache_key]
```

### Key Rotation
- **Master Key**: AWS KMS key rotation enabled (annual automatic rotation).
- **Data Keys**: Refreshed hourly via cache TTL. Old keys retained for decryption.
- **Audit**: All KMS operations logged to CloudTrail with correlation_id.

---

## 8. Observability & Logging

### Structured Logging (structlog)
```python
logger.info("application_submitted",
            correlation_id=correlation_id,
            application_id=app.id,
            client_id=app.client_id,
            broker_id=app.broker_id,
            ltv_ratio=app.ltv_ratio,
            insurance_required=app.insurance_required,
            gds_ratio=gds_calc['gds_ratio'],
            tds_ratio=tds_calc['tds_ratio'],
            qualifying_rate=stress_test_rate,
            # NEVER log: sin, dob, income values
            )
```

### OpenTelemetry Tracing
- Span on each endpoint: `intake.{endpoint_name}`
- Attributes: `application.id`, `client.id`, `broker.id`
- Metrics: `applications_submitted_total`, `gds_ratio_histogram`, `tds_ratio_histogram`

### Prometheus Metrics
```
# /metrics
intake_applications_submitted_total{status="success"} 152
intake_applications_submitted_total{status="rejected"} 23
intake_debt_service_ratio_gds{application_id="..."} 0.38
intake_debt_service_ratio_tds{application_id="..."} 0.42
```

---

## 9. Testing Strategy

### Unit Tests (`tests/unit/test_intake.py`)
- Test validation rules (purchase_price > 0, amortization range)
- Test GDS/TDS calculation with various incomes
- Test CMHC insurance tier logic
- Test encryption/decryption round-trip
- Test state machine transitions

### Integration Tests (`tests/integration/test_intake_integration.py`)
- End-to-end application creation → submission flow
- Authorization: client/broker/admin access controls
- FINTRAC flagging on $10k+ loans
- OSFI limit enforcement with stress test
- PIPEDA compliance: SIN/DOB not in logs or responses

### Test Markers
```bash
uv run pytest -m "unit" tests/unit/test_intake.py
uv run pytest -m "integration" tests/integration/test_intake_integration.py
```

---

## 10. Deployment Checklist

- [ ] Run `uv run pip-audit` before deploy
- [ ] Run Alembic migration `001_create_intake_tables`
- [ ] Verify KMS key policy for `KMS_MASTER_KEY_ID`
- [ ] Update `.env.example` with new config variables
- [ ] Run mypy: `uv run mypy modules/intake/`
- [ ] Run ruff: `uv run ruff check modules/intake/`
- [ ] Load test `/submit` endpoint (CPU-intensive calculations)
- [ ] Verify Prometheus scrape config for new metrics
- [ ] Update API Gateway rate limits for `/applications` routes

---

**Document Version:** 1.0  
**Last Updated:** 2024-01-15  
**Owner:** Design Agent (Complexity: Reasoning)