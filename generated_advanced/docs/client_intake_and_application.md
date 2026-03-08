# Client Intake & Application
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Design Plan: Client Intake & Application Module

**Module ID:** `intake`  
**Feature Slug:** `client-intake-application`  
**Document Path:** `docs/design/client-intake-application.md`

---

## 1. Endpoints

### `POST /api/v1/applications`
Create a new mortgage application (starts in `draft` status).

**Authentication:** Authenticated client or broker

**Request Body (`ApplicationCreate`):**
```python
{
    "client_id": "uuid",  # Required for brokers; inferred from token for clients
    "property_address": "str",  # Encrypted at rest
    "property_type": "Literal['single_family', 'condo', 'townhouse', 'duplex']",
    "property_value": "Decimal(12,2)",  # Required for refinances
    "purchase_price": "Decimal(12,2)",  # Required for purchases
    "down_payment": "Decimal(12,2)",
    "requested_loan_amount": "Decimal(12,2)",
    "amortization_years": "int",  # 5-30 (insured) or 5-25 (uninsured)
    "term_years": "int",  # 1-10
    "mortgage_type": "Literal['fixed', 'variable']",
    "application_type": "Literal['purchase', 'refinance', 'renewal']",
    "co_borrowers": "List[CoBorrowerCreate] | None"
}
```

**Response (`ApplicationResponse`):**
```python
{
    "id": "uuid",
    "status": "draft",
    "client_id": "uuid",
    "broker_id": "uuid | null",
    "property_type": "str",
    "property_value": "Decimal(12,2) | null",
    "purchase_price": "Decimal(12,2) | null",
    "down_payment": "Decimal(12,2)",
    "requested_loan_amount": "Decimal(12,2)",
    "amortization_years": "int",
    "term_years": "int",
    "mortgage_type": "str",
    "application_type": "str",
    "ltv_ratio": "Decimal(5,4)",  # Calculated
    "insurance_required": "bool",  # Based on LTV
    "cmhc_premium_rate": "Decimal(5,4) | null",  # If insurance required
    "created_at": "datetime",
    "updated_at": "datetime",
    "submitted_at": "datetime | null"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger |
|-------------|------------|----------------|---------|
| 401 | `AUTH_001` | "Invalid or missing authentication token" | Missing/invalid JWT |
| 403 | `INTAKE_004` | "Access denied: cannot create application for client" | Broker not assigned to client |
| 422 | `INTAKE_002` | "{field}: {reason}" | Validation failure (e.g., amortization_years out of range) |

---

### `GET /api/v1/applications`
List applications with pagination and filtering.

**Authentication:** Authenticated client or broker

**Query Parameters:**
- `status: str | None` - Filter by application status
- `page: int = 1` - Page number
- `limit: int = 20` - Items per page (max 100)

**Response (`ApplicationListResponse`):**
```python
{
    "items": "List[ApplicationResponse]",
    "total": "int",
    "page": "int",
    "limit": "int"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger |
|-------------|------------|----------------|---------|
| 401 | `AUTH_001` | "Invalid or missing authentication token" | Missing/invalid JWT |

**Access Control:** Clients see only their own applications; brokers see only assigned applications.

---

### `GET /api/v1/applications/{id}`
Get single application details.

**Authentication:** Authenticated client or broker

**Response (`ApplicationResponse`):** Same as POST response

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger |
|-------------|------------|----------------|---------|
| 401 | `AUTH_001` | "Invalid or missing authentication token" | Missing/invalid JWT |
| 403 | `INTAKE_004` | "Access denied: application not assigned" | Client/broker not authorized |
| 404 | `INTAKE_001` | "Application not found" | Invalid UUID or non-existent |

---

### `PUT /api/v1/applications/{id}`
Update draft application. Cannot modify submitted applications.

**Authentication:** Authenticated client or broker

**Request Body (`ApplicationUpdate`):**
```python
{
    "property_address": "str | None",
    "property_type": "str | None",
    "property_value": "Decimal(12,2) | None",
    "purchase_price": "Decimal(12,2) | None",
    "down_payment": "Decimal(12,2) | None",
    "requested_loan_amount": "Decimal(12,2) | None",
    "amortization_years": "int | None",
    "term_years": "int | None",
    "mortgage_type": "str | None"
}
```

**Response (`ApplicationResponse`):** Updated application

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger |
|-------------|------------|----------------|---------|
| 401 | `AUTH_001` | "Invalid or missing authentication token" | Missing/invalid JWT |
| 403 | `INTAKE_004` | "Access denied: cannot modify application" | Not owner or not in draft |
| 404 | `INTAKE_001` | "Application not found" | Invalid UUID |
| 409 | `INTAKE_003` | "Application already submitted" | Status != draft |

---

### `POST /api/v1/applications/{id}/submit`
Submit application for underwriting (triggers status change to `submitted`).

**Authentication:** Authenticated client or broker

**Response (`ApplicationResponse`):** Application with `status: submitted` and `submitted_at` timestamp

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger |
|-------------|------------|----------------|---------|
| 401 | `AUTH_001` | "Invalid or missing authentication token" | Missing/invalid JWT |
| 403 | `INTAKE_004` | "Access denied: cannot submit application" | Not authorized |
| 404 | `INTAKE_001` | "Application not found" | Invalid UUID |
| 409 | `INTAKE_003` | "Application already submitted" | Status != draft |
| 422 | `INTAKE_005` | "Business validation failed: {reason}" | Missing required fields or LTV > 95% |

**Side Effects:** Creates FINTRAC audit log entry; triggers CMHC insurance check; logs GDS/TDS calculation breakdown.

---

### `GET /api/v1/applications/{id}/summary`
Get PDF-ready JSON summary (for document generation).

**Authentication:** Authenticated client or broker

**Response (`ApplicationSummaryResponse`):**
```python
{
    "application_id": "uuid",
    "generated_at": "datetime",
    "client": {
        "user_id": "uuid",
        "employment_status": "str",
        "employer_name": "str",
        "years_employed": "int",
        "annual_income": "Decimal(12,2)",
        "other_income": "Decimal(12,2)",
        "credit_score": "int",
        "marital_status": "str"
        # SIN and DOB excluded
    },
    "co_borrowers": "List[CoBorrowerSummary]",
    "property": {
        "address": "str",  # Decrypted for PDF generation
        "type": "str",
        "value": "Decimal(12,2)",
        "purchase_price": "Decimal(12,2)"
    },
    "loan": {
        "amount": "Decimal(12,2)",
        "down_payment": "Decimal(12,2)",
        "ltv": "Decimal(5,4)",
        "amortization_years": "int",
        "term_years": "int",
        "mortgage_type": "str",
        "insurance_required": "bool",
        "cmhc_premium_rate": "Decimal(5,4) | null"
    },
    "compliance": {
        "gds_ratio": "Decimal(5,4) | null",
        "tds_ratio": "Decimal(5,4) | null",
        "qualifying_rate": "Decimal(5,4) | null",
        "stress_test_passed": "bool | null"
    }
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger |
|-------------|------------|----------------|---------|
| 401 | `AUTH_001` | "Invalid or missing authentication token" | Missing/invalid JWT |
| 403 | `INTAKE_004` | "Access denied" | Not authorized |
| 404 | `INTAKE_001` | "Application not found" | Invalid UUID |

---

### Co-Borrower Sub-Endpoints (Implied)

**`POST /api/v1/applications/{id}/co-borrowers`**
- Add co-borrower to draft application
- Request: `CoBorrowerCreate` (full_name, sin_encrypted, annual_income, employment_status, credit_score)
- Returns updated `ApplicationResponse`

**`DELETE /api/v1/applications/{id}/co-borrowers/{co_borrower_id}`**
- Remove co-borrower from draft application
- Returns updated `ApplicationResponse`

---

## 2. Models & Database

### `clients` Table
```sql
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    sin_encrypted BYTEA NOT NULL,  -- AES-256-GCM encrypted
    sin_hash VARCHAR(64) NOT NULL,  -- SHA256 hex digest for lookups
    date_of_birth_encrypted BYTEA NOT NULL,  -- AES-256-GCM encrypted
    employment_status VARCHAR(50) NOT NULL,  -- employed, self_employed, retired, other
    employer_name VARCHAR(255),
    years_employed INTEGER CHECK (years_employed >= 0),
    annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
    other_income DECIMAL(12,2) DEFAULT 0.00,
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    marital_status VARCHAR(20),  -- single, married, common_law, divorced
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_clients_user_id ON clients(user_id);
CREATE INDEX idx_clients_sin_hash ON clients(sin_hash);
```

**Compliance Notes:**
- `sin_encrypted` and `date_of_birth_encrypted` flagged for AES-256 encryption
- `sin_hash` enables lookup without decryption (PIPEDA compliant)
- No PII logged; audit fields immutable per FINTRAC

---

### `applications` Table
```sql
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    broker_id UUID REFERENCES users(id) ON DELETE SET NULL,
    application_type VARCHAR(20) NOT NULL,  -- purchase, refinance, renewal
    status VARCHAR(20) NOT NULL DEFAULT 'draft',  -- draft, submitted, underwriting, approved, rejected, closed
    property_address_encrypted BYTEA NOT NULL,  -- AES-256-GCM encrypted (PIPEDA)
    property_type VARCHAR(50) NOT NULL,
    property_value DECIMAL(12,2),  -- Nullable for purchases (use purchase_price)
    purchase_price DECIMAL(12,2),  -- Nullable for refinances
    down_payment DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    requested_loan_amount DECIMAL(12,2) NOT NULL CHECK (requested_loan_amount > 0),
    amortization_years INTEGER NOT NULL CHECK (amortization_years BETWEEN 5 AND 30),
    term_years INTEGER NOT NULL CHECK (term_years BETWEEN 1 AND 10),
    mortgage_type VARCHAR(20) NOT NULL,  -- fixed, variable
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ
);

CREATE INDEX idx_applications_client_id ON applications(client_id);
CREATE INDEX idx_applications_broker_id ON applications(broker_id);
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_applications_created_at ON applications(created_at DESC);
CREATE INDEX idx_applications_submitted_at ON applications(submitted_at) WHERE submitted_at IS NOT NULL;
```

**Constraints:**
- `amortization_years` upper bound validated in business logic (25 for uninsured, 30 for insured)
- `property_value` vs `purchase_price` mutual exclusivity enforced in service layer
- `submitted_at` immutable after submission (FINTRAC audit trail)

---

### `co_borrowers` Table
```sql
CREATE TABLE co_borrowers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    sin_encrypted BYTEA NOT NULL,  -- AES-256-GCM encrypted
    sin_hash VARCHAR(64) NOT NULL,
    annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
    employment_status VARCHAR(50) NOT NULL,
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_co_borrowers_application_id ON co_borrowers(application_id);
CREATE INDEX idx_co_borrowers_sin_hash ON co_borrowers(sin_hash);
```

**Relationships:**
- One-to-many: `applications` → `co_borrowers`
- Cascade delete ensures data consistency

---

## 3. Business Logic

### Application Status Workflow
```python
STATE_MACHINE = {
    "draft": {"submit": "submitted"},
    "submitted": {"underwrite": "underwriting", "reject": "rejected"},
    "underwriting": {"approve": "approved", "reject": "rejected", "request_info": "submitted"},
    "approved": {"close": "closed"},
    "rejected": {},  # Terminal state
    "closed": {}  # Terminal state
}
```

**Transition Rules:**
- Only `draft` applications can be modified via `PUT`
- `submit` action triggers OSFI B-20 calculations and CMHC insurance check
- `submitted_at` timestamp set once, immutable thereafter (FINTRAC)

---

### Validation Rules
| Field | Rule | Error Code |
|-------|------|------------|
| `purchase_price` | > 0 | `INTAKE_002` |
| `annual_income` | > 0 | `INTAKE_002` |
| `term_years` | 1-10 inclusive | `INTAKE_002` |
| `amortization_years` | 5-25 (uninsured) or 5-30 (insured) | `INTAKE_002` |
| `requested_loan_amount` | ≤ property_value × 0.95 (max LTV) | `INTAKE_003` |
| `down_payment` | ≥ 5% of purchase_price (if insured) | `INTAKE_003` |
| `credit_score` | 300-900 range | `INTAKE_002` |

---

### CMHC Insurance Calculation
```python
def calculate_cmhc_insurance(loan_amount: Decimal, property_value: Decimal) -> tuple[bool, Decimal | None]:
    ltv = loan_amount / property_value  # Precision: Decimal(5,4)
    if ltv <= Decimal('0.80'):
        return False, None
    
    # Premium tiers (LTV > 80.01%)
    if ltv <= Decimal('0.85'):
        premium_rate = Decimal('0.0280')
    elif ltv <= Decimal('0.90'):
        premium_rate = Decimal('0.0310')
    elif ltv <= Decimal('0.95'):
        premium_rate = Decimal('0.0400')
    else:
        raise IntakeBusinessRuleError("LTV exceeds 95% maximum")
    
    return True, premium_rate
```

---

### OSFI B-20 Stress Test & Ratios
```python
def calculate_gds_tds(
    monthly_payment: Decimal,
    property_tax: Decimal,
    heating: Decimal,
    gross_monthly_income: Decimal,
    other_debt_payments: Decimal = Decimal('0')
) -> tuple[Decimal, Decimal]:
    # PITH = Principal + Interest + Property Tax + Heating
    pith = monthly_payment + property_tax + heating
    
    # GDS = PITH / Gross Monthly Income
    gds = pith / gross_monthly_income  # Must be ≤ 39%
    
    # TDS = (PITH + Other Debt) / Gross Monthly Income
    tds = (pith + other_debt_payments) / gross_monthly_income  # Must be ≤ 44%
    
    return gds, tds

def get_qualifying_rate(contract_rate: Decimal) -> Decimal:
    # OSFI B-20 stress test: max(contract_rate + 2%, 5.25%)
    return max(contract_rate + Decimal('2.0'), Decimal('5.25'))
```

**Audit Logging:** Every ratio calculation logged with breakdown:
```json
{
    "correlation_id": "...",
    "event": "osfi_b20_calculation",
    "application_id": "...",
    "gds_ratio": "0.3500",
    "tds_ratio": "0.4200",
    "qualifying_rate": "5.25",
    "stress_test_passed": true,
    "gds_threshold": "0.39",
    "tds_threshold": "0.44"
}
```

---

## 4. Migrations

### Alembic Revision: `create_intake_tables`

**New Tables:**
1. `clients` - Core client profile with encrypted PII
2. `applications` - Mortgage application header
3. `co_borrowers` - Co-borrower details per application

**Indexes:**
- Composite: `idx_applications_broker_status ON applications(broker_id, status)` for broker dashboard queries
- Partial: `idx_applications_draft_created ON applications(status) WHERE status = 'draft'` for cleanup jobs

**Data Migration:** None (greenfield module)

**Post-Migration Hook:** Verify encryption keys are provisioned before deployment.

---

## 5. Security & Compliance

### PIPEDA Data Handling
- **Encryption at Rest:** `sin_encrypted`, `date_of_birth_encrypted`, `property_address_encrypted` use AES-256-GCM via `common/security.encrypt_pii()`
- **Key Management:** Encryption key from `ENV_SIN_ENCRYPTION_KEY` (32-byte base64). **Strategy:** Rotate keys annually via re-encryption batch job; store key in Azure Key Vault or AWS KMS.
- **Data Minimization:** API responses never include SIN/DOB; only `sin_hash` used for duplicate detection
- **Logging:** Strict prohibition on logging `sin_encrypted`, `date_of_birth_encrypted`, `annual_income`, `other_income`, `property_address_encrypted`

### FINTRAC Compliance
- **Immutable Audit Trail:** `created_at`, `submitted_at` never updated; use `common.database.Base` with `updated_at` tracking
- **Transaction Flagging:** Applications with `requested_loan_amount > 10000` automatically flagged in audit log with `transaction_type: "mortgage_application"`
- **5-Year Retention:** Soft-delete prohibited; archive to cold storage after 5 years via `closed` status batch job

### OSFI B-20 Enforcement
- **Stress Test:** Qualifying rate calculated on `submit`; logged with correlation_id
- **Hard Limits:** GDS ≤ 39%, TDS ≤ 44%; violations raise `IntakeBusinessRuleError` with error code `INTAKE_003`
- **Auditability:** All calculations include `application_id`, `correlation_id`, and timestamp in structured logs

### CMHC Insurance Logic
- **LTV Calculation:** `requested_loan_amount / property_value` (Decimal precision preserved)
- **Premium Lookup:** Automated on `submit`; stored in `cmhc_premium_rate` column
- **Threshold Validation:** LTV > 95% rejected with `INTAKE_003`

### Access Control Matrix
| Role | Create App | View Own | View Assigned | Update Draft | Submit | Delete |
|------|------------|----------|---------------|--------------|--------|--------|
| Client | ✅ | ✅ | ❌ | ✅ Own | ✅ Own | ❌ |
| Broker | ✅ | ❌ | ✅ | ✅ Assigned | ✅ Assigned | ❌ |
| Admin | ✅ | ✅ | ✅ | ✅ Any | ✅ Any | ❌ |

**Implementation:** `services.py` methods decorated with `@require_ownership` and `@require_assignment` using JWT `sub` claim.

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Log Level |
|-----------------|-------------|------------|-----------------|-----------|
| `ApplicationNotFoundError` | 404 | `INTAKE_001` | "Application {id} not found" | INFO |
| `ApplicationValidationError` | 422 | `INTAKE_002` | "{field}: {reason}" | WARNING |
| `ApplicationBusinessRuleError` | 409 | `INTAKE_003` | "Business rule violated: {detail}" | WARNING |
| `ApplicationAccessDeniedError` | 403 | `INTAKE_004` | "Access denied: {resource}" | INFO |
| `ApplicationSubmitError` | 422 | `INTAKE_005` | "Submit failed: {reason}" | ERROR |

### Exception Hierarchy
```python
# modules/intake/exceptions.py
class IntakeException(AppException):
    """Base exception for intake module"""
    module_code = "INTAKE"

class ApplicationNotFoundError(IntakeException):
    http_status = 404
    error_code = "INTAKE_001"

class ApplicationValidationError(IntakeException):
    http_status = 422
    error_code = "INTAKE_002"

class ApplicationBusinessRuleError(IntakeException):
    http_status = 409
    error_code = "INTAKE_003"

class ApplicationAccessDeniedError(IntakeException):
    http_status = 403
    error_code = "INTAKE_004"

class ApplicationSubmitError(IntakeException):
    http_status = 422
    error_code = "INTAKE_005"
```

### Structured Error Response Format
```json
{
    "detail": "Application 123e4567-e89b-12d3-a456-426614174000 not found",
    "error_code": "INTAKE_001",
    "module": "intake",
    "timestamp": "2024-01-15T14:30:00Z",
    "correlation_id": "req-abc123xyz"
}
```

**Logging:** All errors emit JSON logs with `correlation_id`, `user_id`, `application_id` (if applicable), and `error_code` for Splunk/Prometheus alerting.

---

**WARNING:** This module depends on `users` table from authentication module. Ensure foreign key constraints reference the correct schema. If `users` table is in a separate schema (e.g., `auth.users`), use `ForeignKey("auth.users.id")`.