# Client Intake & Application
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Design Plan: Client Intake & Application Module

**File:** `docs/design/client-intake-application.md`  
**Module:** `modules/application/`  
**Date:** 2024 Implementation Cycle

---

## 1. Endpoints

### `POST /api/v1/applications`
Create a new mortgage application (draft status).

**Authentication:** JWT required (client or broker)

**Request Body (`CreateApplicationRequest`):**
```python
{
    "client_id": UUID,                          # Required
    "property_address": str,                    # Required, max 255
    "property_type": PropertyTypeEnum,          # Required: single_family, condo, townhouse, multi_unit, rural
    "property_value": Decimal,                  # Required, > 0
    "purchase_price": Decimal,                  # Required, > 0, ≤ property_value
    "down_payment": Decimal,                    # Required, ≥ 5% of purchase_price (insured) or ≥ 20% (uninsured)
    "requested_loan_amount": Decimal,           # Required, = purchase_price - down_payment
    "amortization_years": int,                  # Required, 5-30 (insured) or 5-25 (uninsured)
    "term_years": int,                          # Required, 1-10
    "mortgage_type": MortgageTypeEnum,          # Required: fixed, variable
    "co_borrowers": List[CoBorrowerCreate],     # Optional
}
```

**Response (`ApplicationResponse`):**
```python
{
    "id": UUID,
    "client_id": UUID,
    "broker_id": UUID,
    "application_type": ApplicationTypeEnum,    # purchase, refinance, renewal, transfer
    "status": ApplicationStatusEnum,            # draft
    "property_address": str,
    "property_type": PropertyTypeEnum,
    "property_value": Decimal,
    "purchase_price": Decimal,
    "down_payment": Decimal,
    "requested_loan_amount": Decimal,
    "amortization_years": int,
    "term_years": int,
    "mortgage_type": MortgageTypeEnum,
    "ltv_ratio": Decimal,                       # Calculated: loan_amount / property_value
    "insurance_required": bool,
    "cmhc_premium_amount": Decimal,             # If insurance_required
    "created_at": datetime,
    "updated_at": datetime,
    "submitted_at": Optional[datetime],
    "co_borrowers": List[CoBorrowerResponse],
}
```

**Error Responses:**
| HTTP | Error Code | Condition |
|------|------------|-----------|
| 401 | AUTH_001 | Missing or invalid JWT token |
| 403 | APP_004 | Client does not own this resource / Broker not assigned |
| 404 | CLI_001 | Client ID not found |
| 422 | APP_002 | Validation failed: purchase_price ≤ 0, amortization out of range, etc. |
| 422 | COB_002 | Co-borrower validation failed |

---

### `GET /api/v1/applications`
List applications with pagination and filtering.

**Authentication:** JWT required

**Query Parameters:**
```python
{
    "status": Optional[ApplicationStatusEnum],
    "page": int = 1,
    "limit": int = 20,  # Max 100
}
```

**Response (`PaginatedApplicationList`):**
```python
{
    "items": List[ApplicationResponse],  # Excludes SIN/DOB
    "total": int,
    "page": int,
    "limit": int,
    "pages": int,
}
```

**Access Control:** Clients receive only their applications; Brokers receive only their assigned applications.

**Error Responses:**
| HTTP | Error Code | Condition |
|------|------------|-----------|
| 401 | AUTH_001 | Invalid token |
| 403 | APP_004 | Insufficient permissions |

---

### `GET /api/v1/applications/{id}`
Retrieve single application details.

**Authentication:** JWT required

**Response:** `ApplicationResponse` (full details, SIN/DOB excluded)

**Error Responses:**
| HTTP | Error Code | Condition |
|------|------------|-----------|
| 401 | AUTH_001 | Invalid token |
| 403 | APP_004 | Not owner or assigned broker |
| 404 | APP_001 | Application not found |

---

### `PUT /api/v1/applications/{id}`
Update application details (draft/returned status only).

**Authentication:** JWT required

**Request Body (`UpdateApplicationRequest`):**
```python
{
    "property_address": Optional[str],
    "property_value": Optional[Decimal],
    "purchase_price": Optional[Decimal],
    "down_payment": Optional[Decimal],
    "amortization_years": Optional[int],
    "term_years": Optional[int],
    "mortgage_type": Optional[MortgageTypeEnum],
    "co_borrowers": Optional[List[CoBorrowerUpdate]],
}
```

**Response:** `ApplicationResponse`

**Business Rule:** Updates only allowed if `status IN ('draft', 'returned')`.

**Error Responses:**
| HTTP | Error Code | Condition |
|------|------------|-----------|
| 400 | APP_003 | Cannot modify submitted/underwriting application |
| 401 | AUTH_001 | Invalid token |
| 403 | APP_004 | Permission denied |
| 404 | APP_001 | Application not found |
| 409 | APP_003 | Business rule violation |

---

### `POST /api/v1/applications/{id}/submit`
Submit application for underwriting review.

**Authentication:** JWT required

**Request Body:** Empty (or optional `{"confirm": bool}` for FINTRAC audit)

**Response (`ApplicationSubmittedResponse`):**
```python
{
    "id": UUID,
    "status": ApplicationStatusEnum,  # submitted
    "submitted_at": datetime,
    "next_steps": str,
}
```

**Business Logic:**
- Validates all required fields populated
- Calculates LTV and insurance requirements
- Transitions status: `draft` → `submitted`
- Logs immutable audit trail (FINTRAC compliance)
- Triggers OSFI B-20 pre-check (GDS/TDS warning flags)

**Error Responses:**
| HTTP | Error Code | Condition |
|------|------------|-----------|
| 400 | APP_003 | Missing required fields |
| 400 | APP_003 | LTV > 95% (uninsurable) |
| 401 | AUTH_001 | Invalid token |
| 403 | APP_004 | Not owner/broker |
| 404 | APP_001 | Application not found |
| 409 | APP_003 | Already submitted |

---

### `GET /api/v1/applications/{id}/summary`
Retrieve PDF-ready JSON summary for document generation.

**Authentication:** JWT required

**Response (`ApplicationSummaryResponse`):**
```python
{
    "application_id": UUID,
    "generated_at": datetime,
    "client": {
        "id": UUID,
        "employment_status": str,
        "employer_name": str,
        "years_employed": int,
        "annual_income": Decimal,
        "other_income": Decimal,
        "credit_score": int,
    },
    "property": {
        "address": str,
        "type": str,
        "value": Decimal,
        "purchase_price": Decimal,
    },
    "mortgage": {
        "loan_amount": Decimal,
        "down_payment": Decimal,
        "ltv_ratio": Decimal,
        "insurance_required": bool,
        "cmhc_premium": Decimal,
        "amortization_years": int,
        "term_years": int,
        "mortgage_type": str,
    },
    "co_borrowers": List[CoBorrowerSummary],
    "declarations": {
        "is_first_time_homebuyer": bool,
        "has_outstanding_judgements": bool,
        "has_declared_bankruptcy": bool,
    },
}
```

**Note:** SIN/DOB never included. Income values included for underwriting summary only.

**Error Responses:**
| HTTP | Error Code | Condition |
|------|------------|-----------|
| 401 | AUTH_001 | Invalid token |
| 403 | APP_004 | Permission denied |
| 404 | APP_001 | Application not found |

---

## 2. Models & Database

### `clients` Table
```sql
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    sin_encrypted BYTEA NOT NULL,  -- AES-256 encrypted
    sin_hash VARCHAR(64) NOT NULL,  -- SHA256 for lookups, indexed
    date_of_birth_encrypted BYTEA NOT NULL,  -- AES-256 encrypted
    employment_status employment_status_enum NOT NULL,
    employer_name VARCHAR(255) NOT NULL,
    years_employed INTEGER NOT NULL CHECK (years_employed >= 0),
    annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
    other_income DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    marital_status marital_status_enum,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    UNIQUE(user_id),
    UNIQUE(sin_hash),
    INDEX idx_clients_user_id (user_id),
    INDEX idx_clients_sin_hash (sin_hash)
);
```

**Encrypted Fields:** `sin_encrypted`, `date_of_birth_encrypted` (AES-256 via `common/security.encrypt_pii()`)

---

### `applications` Table
```sql
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    broker_id UUID REFERENCES users(id) ON DELETE SET NULL,
    application_type application_type_enum NOT NULL DEFAULT 'purchase',
    status application_status_enum NOT NULL DEFAULT 'draft',
    property_address VARCHAR(500) NOT NULL,
    property_type property_type_enum NOT NULL,
    property_value DECIMAL(12,2) NOT NULL CHECK (property_value > 0),
    purchase_price DECIMAL(12,2) NOT NULL CHECK (purchase_price > 0),
    down_payment DECIMAL(12,2) NOT NULL CHECK (down_payment >= 0),
    requested_loan_amount DECIMAL(12,2) NOT NULL CHECK (requested_loan_amount > 0),
    amortization_years INTEGER NOT NULL CHECK (amortization_years BETWEEN 5 AND 30),
    term_years INTEGER NOT NULL CHECK (term_years BETWEEN 1 AND 10),
    mortgage_type mortgage_type_enum NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT chk_loan_amount CHECK (requested_loan_amount = purchase_price - down_payment),
    INDEX idx_applications_client_id (client_id),
    INDEX idx_applications_broker_id (broker_id),
    INDEX idx_applications_status (status),
    INDEX idx_applications_submitted_at (submitted_at),
    INDEX idx_applications_composite (client_id, status)
);
```

**Audit Fields:** `created_at`, `updated_at` (auto-managed by SQLAlchemy event listeners)

---

### `co_borrowers` Table
```sql
CREATE TABLE co_borrowers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    sin_encrypted BYTEA NOT NULL,  -- AES-256 encrypted
    sin_hash VARCHAR(64) NOT NULL,  -- SHA256 for lookups
    annual_income DECIMAL(12,2) NOT NULL CHECK (annual_income > 0),
    employment_status employment_status_enum NOT NULL,
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    INDEX idx_coborrowers_application_id (application_id),
    INDEX idx_coborrowers_sin_hash (sin_hash)
);
```

**Relationships:** One-to-many from applications to co_borrowers.

---

### Enum Types
```sql
CREATE TYPE employment_status_enum AS ENUM ('employed', 'self_employed', 'unemployed', 'retired', 'other');
CREATE TYPE marital_status_enum AS ENUM ('single', 'married', 'common_law', 'divorced', 'widowed');
CREATE TYPE application_type_enum AS ENUM ('purchase', 'refinance', 'renewal', 'transfer');
CREATE TYPE application_status_enum AS ENUM ('draft', 'submitted', 'underwriting', 'approved', 'rejected', 'returned', 'cancelled');
CREATE TYPE property_type_enum AS ENUM ('single_family', 'condo', 'townhouse', 'multi_unit', 'rural', 'commercial');
CREATE TYPE mortgage_type_enum AS ENUM ('fixed', 'variable');
```

---

## 3. Business Logic

### Application Status State Machine
```
[draft] ──submit()──► [submitted] ──assign()──► [underwriting]
   │                       │
   │ update()              │ reject()
   ▼                       ▼
[cancelled]            [rejected]
   ▲                       │
   │                       │ approve()
   │                       ▼
[returned] ◄──return()── [approved]
```

**Transition Rules:**
- `draft` → `submitted`: All required fields validated, LTV ≤ 95%, income > 0
- `submitted` → `underwriting`: Broker/underwriter assignment
- Any status → `cancelled`: Only by client if not yet approved
- `underwriting` → `returned`: Request additional information (returns to client)
- `underwriting` → `approved`/`rejected`: Final decision

### Validation Algorithms

**LTV Calculation:**
```python
ltv_ratio = (requested_loan_amount / property_value) * 100
insurance_required = ltv_ratio > 80.00
```

**CMHC Premium Lookup:**
```python
if 80.01 <= ltv_ratio <= 85.00: premium_rate = Decimal('0.0280')
elif 85.01 <= ltv_ratio <= 90.00: premium_rate = Decimal('0.0310')
elif 90.01 <= ltv_ratio <= 95.00: premium_rate = Decimal('0.0400')
else: premium_rate = Decimal('0')
cmhc_premium_amount = requested_loan_amount * premium_rate
```

**Amortization Validation:**
```python
if ltv_ratio > 80.00:  # Insured
    assert 5 <= amortization_years <= 30
else:  # Uninsured
    assert 5 <= amortization_years <= 25
```

**OSFI B-20 Pre-check (Intake):**
- Log warning if estimated GDS would exceed 39% or TDS exceed 44% using qualifying_rate = max(contract_rate + 2%, 5.25%)
- Does not reject at intake, but flags for underwriter
- Calculation: `gds_estimate = (pith_monthly / gross_monthly_income) * 100`

### Co-Borrower Management
- Add/remove only when `status = 'draft'`
- Income aggregation: `total_household_income = client.annual_income + sum(coborrower.annual_income)`
- SIN encrypted identically to client SIN
- On submit, co-borrower data becomes immutable (FINTRAC audit)

---

## 4. Migrations

### Alembic Revision: `create_client_intake_tables`
```python
# Create all enum types first
op.execute("CREATE TYPE employment_status_enum AS ENUM (...);")
op.execute("CREATE TYPE application_status_enum AS ENUM (...);")

# Create clients table
op.create_table('clients', ...)
op.create_index('idx_clients_user_id', 'clients', ['user_id'])
op.create_index('idx_clients_sin_hash', 'clients', ['sin_hash'])

# Create applications table
op.create_table('applications', ...)
op.create_index('idx_applications_client_id', 'applications', ['client_id'])
op.create_index('idx_applications_broker_id', 'applications', ['broker_id'])
op.create_index('idx_applications_status', 'applications', ['status'])
op.create_index('idx_applications_composite', 'applications', ['client_id', 'status'])

# Create co_borrowers table
op.create_table('co_borrowers', ...)
op.create_index('idx_coborrowers_application_id', 'co_borrowers', ['application_id'])

# Add updated_at trigger function
op.execute("""
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""")

op.execute("""
CREATE TRIGGER update_applications_updated_at
BEFORE UPDATE ON applications
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
""")
```

### Data Migration Needs
- **None** for initial creation. Future migrations must preserve 5-year FINTRAC retention.

---

## 5. Security & Compliance

### PIPEDA Compliance
- **Encryption at Rest:** SIN and DOB encrypted with AES-256-GCM via `common/security.encrypt_pii()` before storage
- **Key Management:** Encryption keys stored in HashiCorp Vault, rotated quarterly
- **Data Minimization:** Only collect employment, income, and credit fields required for underwriting
- **No Logging:** SIN, DOB, income values never logged; use `sin_hash` for debugging
- **API Responses:** Never return encrypted fields or hashes to client

### FINTRAC Requirements
- **Immutable Audit Trail:** All `INSERT` operations logged to `audit_log` table with `created_by` user ID
- **5-Year Retention:** `applications` and `co_borrowers` rows never physically deleted; marked `cancelled` and archived to cold storage after 5 years
- **Transaction Reporting:** Applications with `purchase_price > 10000` automatically flagged with `large_transaction=True` in audit log
- **Identity Verification:** Client identity verification event logged before application submission

### OSFI B-20 Integration
- **Stress Test Pre-Check:** Intake module calculates estimated GDS/TDS using qualifying rate and logs breakdown
- **Hard Limits:** If LTV > 95%, reject at submit (uninsurable)
- **Audit Logging:** All ratio calculations logged with `correlation_id` for regulator audit

### Authentication & Authorization
- **JWT Required:** All endpoints require valid `Authorization: Bearer <token>` header
- **Scope-Based Access:**
  - `client` role: Can only `GET/POST/PUT` own applications
  - `broker` role: Can only access applications where `broker_id = self.id`
  - `underwriter` role: Read-only access to all submitted applications
- **Row-Level Security:** PostgreSQL RLS policies enforce access control at database level

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy
```python
# In modules/application/exceptions.py
class ApplicationException(AppException):
    """Base exception for application module"""
    pass

class ApplicationNotFoundError(ApplicationException):
    """Application ID does not exist"""
    pass

class ApplicationValidationError(ApplicationException):
    """Pydantic or business validation failed"""
    pass

class ApplicationBusinessRuleError(ApplicationException):
    """State transition or underwriting rule violated"""
    pass

class ApplicationPermissionError(ApplicationException):
    """User lacks access to this application"""
    pass
```

### Error Code Mapping
| Exception Class | HTTP Status | Error Code | Message Pattern | Log Level |
|-----------------|-------------|------------|-----------------|-----------|
| `ApplicationNotFoundError` | 404 | APP_001 | "Application {id} not found" | WARNING |
| `ApplicationValidationError` | 422 | APP_002 | "{field}: {reason}" | INFO |
| `ApplicationBusinessRuleError` | 409 | APP_003 | "{rule} violated: {detail}" | WARNING |
| `ApplicationPermissionError` | 403 | APP_004 | "Access denied to application {id}" | WARNING |
| `ClientNotFoundError` | 404 | CLI_001 | "Client {client_id} not found" | WARNING |
| `CoBorrowerValidationError` | 422 | COB_002 | "Co-borrower {index}: {reason}" | INFO |
| `AuthenticationError` | 401 | AUTH_001 | "Invalid or expired token" | INFO |

### Structured Error Response Format
All errors return consistent JSON:
```json
{
    "detail": "Application business rule violated: Cannot modify submitted application",
    "error_code": "APP_003",
    "correlation_id": "req-550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T14:30:00Z"
}
```

### Edge Cases & Specific Errors
- **LTV > 95%:** `APP_003` "Loan-to-value ratio exceeds 95% - uninsurable"
- **Amortization > 25 years for uninsured:** `APP_002` "amortization_years: Maximum 25 for uninsured mortgages"
- **Down payment < 5%:** `APP_002` "down_payment: Minimum 5% of purchase price required"
- **Duplicate SIN hash:** `APP_002` "sin_hash: Client with this SIN already exists"
- **Submit non-draft:** `APP_003` "Status transition from {current} to submitted not allowed"

---

## Implementation Notes

1. **SIN Encryption Strategy:** Use deterministic AES-256-GCM with separate key per client; store nonce with ciphertext; rotate keys via Vault
2. **Default Values:** `application_type` defaults to 'purchase'; `status` defaults to 'draft'
3. **Co-borrower Removal:** Implemented as soft-delete (marked inactive) to maintain FINTRAC audit
4. **Performance:** Add Redis cache for `GET /applications/{id}` with 5-minute TTL, invalidated on update
5. **Testing:** Unit tests must mock `encrypt_pii()`; integration tests must verify SIN never appears in logs

**Next Steps:** Proceed to implementation phase after design review approval from compliance team.