# Client Intake & Application
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Client Intake & Application Module Design Plan

**Module Path:** `modules/intake/`  
**Feature Slug:** `client-intake-application`  
**Design Document:** `docs/design/client-intake-application.md`

---

## 1. Endpoints

### `POST /api/v1/applications`
Create a new mortgage application (draft status).

**Authentication:** Authenticated (client or broker)  
**Authorization:** Client can create for self; broker can create on behalf of assigned clients

**Request Body (`CreateApplicationSchema`):**
```json
{
  "client_id": "uuid",
  "property_address": {
    "street": "str",
    "city": "str",
    "province": "str",
    "postal_code": "str"
  },
  "property_type": "enum[single_family, condo, townhouse, multi_unit, commercial]",
  "property_value": "Decimal",
  "purchase_price": "Decimal",
  "down_payment": "Decimal",
  "requested_loan_amount": "Decimal",
  "amortization_years": "int (5-30)",
  "term_years": "int (1-10)",
  "mortgage_type": "enum[fixed, variable, adjustable]",
  "application_type": "enum[purchase, refinance, renewal, transfer]",
  "co_borrowers": [
    {
      "full_name": "str",
      "sin_encrypted": "bytes",
      "annual_income": "Decimal",
      "employment_status": "enum[employed, self_employed, unemployed, retired]",
      "credit_score": "int"
    }
  ]
}
```

**Response (`ApplicationSchema`):**
```json
{
  "id": "uuid",
  "client_id": "uuid",
  "broker_id": "uuid|null",
  "status": "draft",
  "property_address": {...},
  "property_type": "single_family",
  "property_value": "Decimal",
  "purchase_price": "Decimal",
  "down_payment": "Decimal",
  "requested_loan_amount": "Decimal",
  "ltv_ratio": "Decimal",
  "cmhc_insurance_required": "bool",
  "cmhc_insurance_premium": "Decimal|null",
  "amortization_years": 25,
  "term_years": 5,
  "mortgage_type": "fixed",
  "application_type": "purchase",
  "created_at": "datetime",
  "updated_at": "datetime",
  "submitted_at": "datetime|null",
  "co_borrowers": [...]
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 401 | `AUTH_001` | Missing or invalid JWT token |
| 403 | `INTAKE_001` | Broker not assigned to client |
| 422 | `INTAKE_002` | `purchase_price` ≤ 0 or `annual_income` ≤ 0 |
| 422 | `INTAKE_003` | `amortization_years` outside allowed range |
| 422 | `INTAKE_004` | LTV > 95% (unqualified for insurance) |

---

### `GET /api/v1/applications`
List applications with pagination and filtering.

**Authentication:** Authenticated  
**Authorization:** Clients see own; brokers see assigned

**Query Parameters:**
- `status?: string` - Filter by status
- `page?: int (default: 1)`
- `limit?: int (default: 20, max: 100)`

**Response (`PaginatedApplicationListSchema`):**
```json
{
  "items": [ApplicationSchema],
  "total": "int",
  "page": "int",
  "limit": "int"
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 401 | `AUTH_001` | Missing or invalid JWT token |

---

### `GET /api/v1/applications/{id}`
Get single application by ID.

**Authentication:** Authenticated  
**Authorization:** Client must own; broker must be assigned

**Response:** `ApplicationSchema`

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 401 | `AUTH_001` | Missing or invalid JWT token |
| 403 | `INTAKE_005` | Access denied to application |
| 404 | `INTAKE_006` | Application not found |

---

### `PUT /api/v1/applications/{id}`
Update draft application. Forbidden after submission.

**Authentication:** Authenticated  
**Authorization:** Client owns; broker assigned

**Request Body (`UpdateApplicationSchema`):** Partial of `CreateApplicationSchema` (excluding `client_id`)

**Response:** `ApplicationSchema`

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 401 | `AUTH_001` | Missing or invalid JWT token |
| 403 | `INTAKE_005` | Access denied |
| 403 | `INTAKE_007` | Cannot modify after submission |
| 404 | `INTAKE_006` | Application not found |
| 409 | `INTAKE_008` | Application already submitted |
| 422 | `INTAKE_002` | Validation failed |

---

### `POST /api/v1/applications/{id}/submit`
Submit application for underwriting. Triggers validation, audit log, and FINTRAC checks.

**Authentication:** Authenticated  
**Authorization:** Client owns; broker assigned

**Request Body:** `{}` (empty) or optional declaration schema

**Response:** `ApplicationSchema` (status: `submitted`)

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 401 | `AUTH_001` | Missing or invalid JWT token |
| 403 | `INTAKE_005` | Access denied |
| 404 | `INTAKE_006` | Application not found |
| 409 | `INTAKE_009` | Application already submitted |
| 422 | `INTAKE_010` | GDS/TDS exceeds OSFI limits |
| 422 | `INTAKE_011` | Missing required co-borrower data |

---

### `GET /api/v1/applications/{id}/summary`
Get PDF-ready JSON summary for document generation.

**Authentication:** Authenticated  
**Authorization:** Client owns; broker assigned

**Response (`ApplicationSummarySchema`):**
```json
{
  "application_id": "uuid",
  "generated_at": "datetime",
  "client": {
    "full_name": "str",
    "employment_status": "str",
    "years_employed": "Decimal",
    "gross_annual_income": "Decimal",
    "credit_score": "int"
  },
  "property": {...},
  "loan_details": {
    "ltv_ratio": "Decimal",
    "cmhc_insurance_premium": "Decimal|null",
    "qualifying_rate": "Decimal",
    "gds_ratio": "Decimal",
    "tds_ratio": "Decimal"
  },
  "compliance_flags": ["FINTRAC_REPORTABLE", "CMHC_INSURED"]
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 401 | `AUTH_001` | Missing or invalid JWT token |
| 403 | `INTAKE_005` | Access denied |
| 404 | `INTAKE_006` | Application not found |

---

## 2. Models & Database

### `clients` Table
```python
Table: clients
- id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- user_id: UUID NOT NULL FOREIGN KEY (users.id) ON DELETE CASCADE
- sin_encrypted: BYTEA NOT NULL  # AES-256-GCM encrypted
- sin_hash: VARCHAR(64) NOT NULL UNIQUE  # SHA256 for lookups
- date_of_birth_encrypted: BYTEA NOT NULL  # AES-256-GCM encrypted
- employment_status: VARCHAR(20) NOT NULL CHECK (employment_status IN ('employed', 'self_employed', 'unemployed', 'retired'))
- employer_name: VARCHAR(255)
- years_employed: NUMERIC(4,2)
- annual_income: DECIMAL(12,2) NOT NULL CHECK (annual_income > 0)
- other_income: DECIMAL(12,2) DEFAULT 0.00
- credit_score: INTEGER CHECK (credit_score BETWEEN 300 AND 900)
- marital_status: VARCHAR(20) CHECK (marital_status IN ('single', 'married', 'common_law', 'divorced', 'widowed'))
- created_at: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
- updated_at: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
- created_by: UUID NOT NULL  # Audit trail for FINTRAC

Indexes:
- idx_clients_user_id (user_id)
- idx_clients_sin_hash (sin_hash)  # For FINTRAC lookups without decryption
```

**Relationships:** One-to-many with `applications`

---

### `applications` Table
```python
Table: applications
- id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- client_id: UUID NOT NULL FOREIGN KEY (clients.id) ON DELETE RESTRICT
- broker_id: UUID FOREIGN KEY (users.id) ON DELETE SET NULL
- application_type: VARCHAR(20) NOT NULL CHECK (application_type IN ('purchase', 'refinance', 'renewal', 'transfer'))
- status: VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'underwriting', 'approved', 'rejected', 'conditions', 'closed'))
- property_address: JSONB NOT NULL  # {street, city, province, postal_code}
- property_type: VARCHAR(30) NOT NULL CHECK (property_type IN ('single_family', 'condo', 'townhouse', 'multi_unit', 'commercial'))
- property_value: DECIMAL(12,2) NOT NULL CHECK (property_value > 0)
- purchase_price: DECIMAL(12,2) CHECK (purchase_price > 0)
- down_payment: DECIMAL(12,2) NOT NULL CHECK (down_payment >= 0)
- requested_loan_amount: DECIMAL(12,2) NOT NULL CHECK (requested_loan_amount > 0)
- amortization_years: INTEGER NOT NULL CHECK (amortization_years BETWEEN 5 AND 30)
- term_years: INTEGER NOT NULL CHECK (term_years BETWEEN 1 AND 10)
- mortgage_type: VARCHAR(20) NOT NULL CHECK (mortgage_type IN ('fixed', 'variable', 'adjustable'))
- interest_rate: DECIMAL(5,4)  # Stored for audit
- qualifying_rate: DECIMAL(5,4)  # OSFI stress test rate
- gds_ratio: DECIMAL(5,4)  # Gross Debt Service ratio
- tds_ratio: DECIMAL(5,4)  # Total Debt Service ratio
- cmhc_insurance_required: BOOLEAN NOT NULL DEFAULT false
- cmhc_insurance_premium: DECIMAL(12,2) DEFAULT 0.00
- fintrac_transaction_id: VARCHAR(50)  # Generated for >$10K
- created_at: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
- updated_at: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
- submitted_at: TIMESTAMP WITH TIME ZONE
- created_by: UUID NOT NULL  # FINTRAC audit

Indexes:
- idx_applications_client_id (client_id)
- idx_applications_broker_id (broker_id)
- idx_applications_status (status)
- idx_applications_submitted_at (submitted_at)
- idx_applications_ltv ((requested_loan_amount / property_value))  # For CMHC queries
```

**Relationships:** Many-to-one with `clients`, one-to-many with `co_borrowers`

---

### `co_borrowers` Table
```python
Table: co_borrowers
- id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
- application_id: UUID NOT NULL FOREIGN KEY (applications.id) ON DELETE CASCADE
- full_name: VARCHAR(255) NOT NULL
- sin_encrypted: BYTEA NOT NULL  # AES-256-GCM encrypted
- sin_hash: VARCHAR(64) NOT NULL  # SHA256 for FINTRAC
- annual_income: DECIMAL(12,2) NOT NULL CHECK (annual_income > 0)
- employment_status: VARCHAR(20) CHECK (employment_status IN ('employed', 'self_employed', 'unemployed', 'retired'))
- credit_score: INTEGER CHECK (credit_score BETWEEN 300 AND 900)
- created_at: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
- updated_at: TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()

Indexes:
- idx_co_borrowers_application_id (application_id)
- idx_co_borrowers_sin_hash (sin_hash)
```

**Relationships:** Many-to-one with `applications`

---

## 3. Business Logic

### Application Status State Machine
```
[draft] → submit() → [submitted] → underwriter_assigned() → [underwriting] →
  ├─ approve() → [approved] → fund() → [closed]
  ├─ reject() → [rejected]
  └─ conditions() → [conditions] → conditions_met() → [approved]
```

**Transition Rules:**
- Only `draft` → `submitted` allowed for POST /submit
- `submitted_at` timestamp set on transition
- Immutable after submission (except status updates by underwriters)

---

### Validation & Calculation Algorithms

**LTV Calculation:**
```python
ltv = requested_loan_amount / property_value  # Decimal division, no rounding
ltv_percent = ltv * 100
```

**CMHC Insurance Premium (if LTV > 80%):**
```python
if 80.01 <= ltv_percent <= 85.00:
    premium_rate = Decimal('0.0280')
elif 85.01 <= ltv_percent <= 90.00:
    premium_rate = Decimal('0.0310')
elif 90.01 <= ltv_percent <= 95.00:
    premium_rate = Decimal('0.0400')
else:
    raise ValidationError("LTV exceeds insurable limit")
    
premium = requested_loan_amount * premium_rate
```

**OSFI B-20 Stress Test & GDS/TDS:**
```python
# Qualifying rate = max(contract_rate + 2%, 5.25%)
qualifying_rate = max(contract_rate + Decimal('0.02'), Decimal('0.0525'))

# Monthly qualifying payment (PITH)
# Use standard mortgage formula with qualifying_rate
monthly_payment = calculate_pmt(qualifying_rate, amortization_years, requested_loan_amount)

# GDS = (PITH) / Gross Monthly Income
gross_monthly_income = total_annual_income / 12
gds = (monthly_payment + monthly_property_tax + monthly_heating) / gross_monthly_income

# TDS = (PITH + Other Debt) / Gross Monthly Income
tds = (monthly_payment + monthly_property_tax + monthly_heating + other_debt) / gross_monthly_income

# Hard limits
if gds > Decimal('0.39') or tds > Decimal('0.44'):
    raise BusinessRuleError("OSFI B-20 ratios exceeded")
```

**Audit Logging:** Every calculation logged with correlation_id, but NO PII values.

---

### Co-Borrower Management
- **Add:** Included in `POST` or `PUT` requests; max 3 co-borrowers
- **Remove:** Set `annual_income` to 0 and mark inactive (never delete per FINTRAC)
- **Update:** Only in `draft` status; requires full re-validation

---

## 4. Migrations

### Alembic Revision: `create_intake_tables`

**New Tables:**
1. `clients`
2. `applications`
3. `co_borrowers`

**Indexes:**
- All indexes listed in Models section
- Composite index: `idx_applications_client_status (client_id, status)` for dashboard queries

**Data Migration:**
- None (new module)

**Post-Migration Hook:**
- Verify encryption keys are loaded in environment
- Run `GRANT SELECT ON clients.sin_hash TO fintrac_service_role;`

---

## 5. Security & Compliance

### PIPEDA Compliance
- **Encryption:** SIN and DOB encrypted with AES-256-GCM via `common/security.encrypt_pii()` 
- **Key Management:** Use AWS KMS or HashiCorp Vault (never hardcode)
- **Data Minimization:** Only collect fields in `clients` table; no SIN in logs/responses
- **Hashing:** `sin_hash` column used for duplicate detection and FINTRAC reporting

### FINTRAC Compliance
- **Audit Trail:** `created_at`, `created_by` on all tables; immutable records
- **Transaction Reporting:** If `requested_loan_amount` ≥ CAD $10,000, set `fintrac_transaction_id` and trigger reporting event
- **Retention:** All records kept for 5 years; soft-delete only via `status='closed'`
- **Logging:** Log `fintrac_transaction_id` but NOT amounts or PII

### OSFI B-20 Compliance
- **Stress Test:** `qualifying_rate` calculated on every submission
- **Ratio Limits:** Hard enforcement: GDS ≤ 39%, TDS ≤ 44%
- **Auditability:** Log calculation inputs (rates, incomes, debts) with correlation_id; exclude actual income values

### CMHC Compliance
- **LTV Precision:** Use Decimal with 4 decimal places; no float rounding
- **Premium Calculation:** Applied automatically when LTV > 80%
- **Amortization Limits:** Enforce 25-year max for uninsured (LTV ≤ 80%)

### Authorization Matrix
| Endpoint | Client | Broker | Admin |
|----------|--------|--------|-------|
| POST /applications | ✓ (self) | ✓ (assigned) | ✓ |
| GET /applications | ✓ (own) | ✓ (assigned) | ✓ (all) |
| GET /applications/{id} | ✓ (own) | ✓ (assigned) | ✓ |
| PUT /applications/{id} | ✓ (own draft) | ✓ (assigned draft) | ✓ |
| POST /applications/{id}/submit | ✓ (own draft) | ✓ (assigned draft) | ✓ |
| GET /applications/{id}/summary | ✓ (own) | ✓ (assigned) | ✓ |

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy
```python
# Base exception from common.exceptions.AppException
class IntakeException(AppException):
    module_code = "INTAKE"

class ApplicationNotFoundError(IntakeException):
    """Raised when application ID does not exist"""
    
class ApplicationValidationError(IntakeException):
    """Raised when field validation fails"""
    
class ApplicationBusinessRuleError(IntakeException):
    """Raised when OSFI, CMHC, or FINTRAC rules violated"""
    
class ApplicationAccessDeniedError(IntakeException):
    """Raised when user lacks authorization"""
```

### Error Code Mapping
| Exception Class | HTTP Status | Error Code | Message Pattern | Log Level |
|-----------------|-------------|------------|-----------------|-----------|
| `ApplicationNotFoundError` | 404 | `INTAKE_001` | "Application {id} not found" | WARNING |
| `ApplicationValidationError` | 422 | `INTAKE_002` | "{field}: {reason}" | INFO |
| `ApplicationBusinessRuleError` | 409 | `INTAKE_003` | "Business rule violated: {detail}" | WARNING |
| `ApplicationAccessDeniedError` | 403 | `INTAKE_004` | "Access denied to application {id}" | WARNING |
| `ApplicationAlreadySubmittedError` | 409 | `INTAKE_005` | "Application already submitted" | INFO |
| `OsfRatioExceededError` | 422 | `INTAKE_006` | "GDS/TDS exceeds OSFI limits: GDS={gds}%, TDS={tds}%" | WARNING |
| `FintracReportingError` | 500 | `INTAKE_007` | "FINTRAC reporting failed: {detail}" | ERROR |

### Structured Error Response Format
```json
{
  "detail": "Application 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "INTAKE_001",
  "correlation_id": "af3d7c9a-1b2c-3d4e-5f6a-7b8c9d0e1f2a",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

---

## Additional Implementation Notes

### SIN Encryption Key Management
- **Strategy:** Use envelope encryption
  1. Master key in AWS KMS (key rotation every 90 days)
  2. Data encryption key (DEK) per record or per batch
  3. Store encrypted DEK alongside `sin_encrypted` in separate column `sin_key_id`
- **Environment:** `SIN_ENCRYPTION_KEY_ARN` in `common/config.py`
- **Rotation:** New keys apply to new records; old keys retained for decryption

### Default Values & Enums
- `application_type`: `purchase`
- `mortgage_type`: `fixed`
- `status`: `draft`
- `property_type`: `single_family`

### Performance Considerations
- Use `selectinload()` for co-borrowers to avoid N+1 queries
- Cache CMHC premium rates in Redis (key: `cmhc:premium_tiers`)
- Index `property_address` as `GIN` index for future geospatial queries

### Observability
- **Metrics:** `intake_applications_submitted_total`, `intake_osfi_rejection_ratio`, `intake_cmhc_insured_total`
- **Traces:** Span per validation step (LTV, CMHC, OSFI)
- **Logs:** Log `application_id`, `status`, `ltv_ratio` but NO PII

---

**Next Steps:** Implementation tickets to be created for `models.py`, `schemas.py`, `services.py`, `routes.py`, and `exceptions.py` with associated unit and integration tests.