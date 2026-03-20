# Orchestrator Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Orchestrator Service Design Plan

**File**: `docs/design/orchestrator-service.md`

---

## 1. Endpoints

### 1.1 Application Management

#### `POST /api/v1/applications`
Submit a new mortgage application with borrower details and PDF documents.

**Authentication**: Authenticated (lender or broker user)

**Request Body** (`schemas.ApplicationSubmitRequest`):
```python
{
  "lender_id": "uuid",  # Required
  "property_value": "Decimal(12,2)",  # Required, > 0
  "purchase_price": "Decimal(12,2)",  # Required, > 0
  "mortgage_amount": "Decimal(12,2)",  # Required, > 0
  "borrower": {
    "full_name": "str",  # Required, max 200 chars
    "sin": "str",  # Required, 9 digits, encrypted at rest
    "date_of_birth": "date",  # Required, encrypted at rest
    "employment_type": "enum[salaried|self-employed|contract]",  # Required
    "gross_annual_income": "Decimal(12,2)",  # Required, > 0
    "credit_score": "int"  # Optional, 300-900
  },
  "documents": [
    {
      "document_type": "enum[paystub|t4|notice_of_assessment|bank_statement|property_appraisal]",  # Required
      "file_name": "str",  # Required
      "file_content": "bytes"  # Required, PDF only, max 10MB
    }
  ]
}
```

**Response** (`schemas.ApplicationSubmitResponse`):
```python
{
  "application_id": "uuid",
  "status": "submitted",
  "created_at": "datetime",
  "message": "Application submitted successfully. Processing initiated."
}
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | ORCHESTRATOR_002 | Invalid file type or size > 10MB |
| 422 | ORCHESTRATOR_002 | Mortgage amount > purchase_price, or LTV > 95% |
| 422 | ORCHESTRATOR_002 | Invalid SIN format or credit_score range |
| 409 | ORCHESTRATOR_003 | Borrower SIN hash already has active application |

---

#### `GET /api/v1/applications/{id}`
Retrieve application status, decision, and summary details.

**Authentication**: Authenticated (owner or admin)

**Response** (`schemas.ApplicationResponse`):
```python
{
  "id": "uuid",
  "borrower": {
    "id": "uuid",
    "full_name": "str",
    "employment_type": "enum",
    "gross_annual_income": "Decimal(12,2)",
    "credit_score": "int"
    # SIN and DOB are never returned
  },
  "lender_id": "uuid",
  "status": "enum[submitted|extracting|evaluating|decided|exception]",
  "property_value": "Decimal(12,2)",
  "purchase_price": "Decimal(12,2)",
  "mortgage_amount": "Decimal(12,2)",
  "ltv_ratio": "Decimal(5,4)",
  "insurance_required": "bool",
  "insurance_premium": "Decimal(12,2)",
  "gds_ratio": "Decimal(5,4)",
  "tds_ratio": "Decimal(5,4)",
  "qualifying_rate": "Decimal(5,4)",
  "decision": "enum[approved|rejected|pending|exception]",
  "decision_reason": "str",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | ORCHESTRATOR_001 | Application ID not found |
| 403 | SECURITY_001 | User lacks permission to view application |

---

#### `GET /api/v1/applications/{id}/documents`
List all uploaded documents for an application.

**Authentication**: Authenticated (owner or admin)

**Response** (`schemas.DocumentListResponse`):
```python
{
  "application_id": "uuid",
  "documents": [
    {
      "id": "uuid",
      "document_type": "enum",
      "file_name": "str",
      "s3_key": "str",  # MinIO/S3 object key
      "uploaded_at": "datetime",
      "status": "enum[pending|processed|failed]"
    }
  ]
}
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | ORCHESTRATOR_001 | Application ID not found |

---

#### `POST /api/v1/applications/{id}/reprocess`
Trigger reprocessing of an application after correction.

**Authentication**: Authenticated (admin or underwriter)

**Request Body** (`schemas.ReprocessRequest`):
```python
{
  "reason": "str",  # Required, min 10 chars
  "preserve_documents": "bool"  # Optional, default true
}
```

**Response** (`schemas.ReprocessResponse`):
```python
{
  "application_id": "uuid",
  "new_task_id": "uuid",
  "status": "submitted",
  "message": "Reprocessing initiated"
}
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | ORCHESTRATOR_001 | Application ID not found |
| 409 | ORCHESTRATOR_003 | Application not in 'decided' or 'exception' state |
| 422 | ORCHESTRATOR_002 | Reason too short |

---

#### `GET /api/v1/applications`
List all applications with pagination and filtering.

**Authentication**: Authenticated (lender admin)

**Query Parameters**:
- `page`: int (default 1)
- `limit`: int (default 20, max 100)
- `status`: enum (optional)
- `borrower_id`: uuid (optional)
- `lender_id`: uuid (optional)

**Response** (`schemas.ApplicationListResponse`):
```python
{
  "total": "int",
  "page": "int",
  "limit": "int",
  "items": ["Array of ApplicationResponse"]
}
```

---

### 1.2 FINTRAC Compliance

#### `POST /api/v1/fintrac/applications/{id}/verify-identity`
Submit identity verification result for FINTRAC compliance.

**Authentication**: Authenticated (underwriter)

**Request Body** (`schemas.IdentityVerificationRequest`):
```python
{
  "verification_method": "enum[documentary|electronic|dual_process]",  # Required
  "verification_result": "enum[passed|failed]",  # Required
  "verified_by": "str",  # Required, employee ID
  "notes": "str"  # Optional
}
```

**Response** (`schemas.IdentityVerificationResponse`):
```python
{
  "verification_id": "uuid",
  "application_id": "uuid",
  "verified_at": "datetime",
  "status": "recorded",
  "message": "Identity verification logged for FINTRAC"
}
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | ORCHESTRATOR_001 | Application ID not found |
| 409 | ORCHESTRATOR_006 | Verification already recorded for application |

---

#### `GET /api/v1/fintrac/applications/{id}/verification`
Get FINTRAC identity verification status.

**Authentication**: Authenticated (owner or admin)

**Response** (`schemas.VerificationStatusResponse`):
```python
{
  "application_id": "uuid",
  "verification_recorded": "bool",
  "verification_method": "enum",
  "verification_result": "enum",
  "verified_at": "datetime",
  "compliant": "bool"
}
```

---

#### `POST /api/v1/fintrac/applications/{id}/report-transaction`
File FINTRAC transaction report for large transactions.

**Authentication**: Authenticated (admin)

**Request Body** (`schemas.TransactionReportRequest`):
```python
{
  "transaction_amount": "Decimal(12,2)",  # Required
  "transaction_type": "enum[purchase|refinance|renewal]",  # Required
  "funds_source": "str",  # Required if amount > 10000
  "third_party_involved": "bool"  # Required if amount > 10000
}
```

**Response** (`schemas.TransactionReportResponse`):
```python
{
  "report_id": "uuid",
  "application_id": "uuid",
  "fntrac_report_id": "str",  # Generated FINTRAC reference
  "threshold_exceeded": "bool",
  "reported_at": "datetime"
}
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | ORCHESTRATOR_007 | Amount > $10,000 but missing funds_source |
| 404 | ORCHESTRATOR_001 | Application ID not found |

---

#### `GET /api/v1/fintrac/risk-assessment/{client_id}`
Get aggregated risk assessment for a client across all applications.

**Authentication**: Authenticated (admin)

**Response** (`schemas.RiskAssessmentResponse`):
```python
{
  "client_id": "uuid",
  "total_applications": "int",
  "high_value_transactions": "int",  # Count > $10,000
  "identity_verifications": "int",
  "risk_score": "int",  # 0-100
  "risk_factors": ["str"],
  "last_updated": "datetime"
}
```

---

## 2. Models & Database

### 2.1 Core Models

#### `orchestrator_applications`
```python
__tablename__ = "orchestrator_applications"

id: UUID(pk)
borrower_id: UUID(FK→orchestrator_borrowers.id, index)
lender_id: UUID(FK→lenders.id, index)
status: Enum(submitted, extracting, evaluating, decided, exception) + index
property_value: Decimal(12,2) + NotNull + Check > 0
purchase_price: Decimal(12,2) + NotNull + Check > 0
mortgage_amount: Decimal(12,2) + NotNull + Check > 0
ltv_ratio: Decimal(5,4) + Computed(mortgage_amount / property_value)
insurance_required: Boolean + Default False
insurance_premium: Decimal(12,2) + Default 0.00
gds_ratio: Decimal(5,4) + Nullable
tds_ratio: Decimal(5,4) + Nullable
qualifying_rate: Decimal(5,4) + Nullable
decision: Enum(approved, rejected, pending, exception) + Nullable + index
decision_reason: Text + Nullable
created_at: DateTime + NotNull + default now() + index
updated_at: DateTime + NotNull + default now() + onupdate now()

# Composite indexes
Index('idx_app_borrower_status', borrower_id, status)
Index('idx_app_lender_decision', lender_id, decision)
Index('idx_app_status_created', status, created_at.desc())
```

#### `orchestrator_borrowers`
```python
__tablename__ = "orchestrator_borrowers"

id: UUID(pk)
full_name: String(200) + NotNull
sin_hash: String(64) + NotNull + Unique + index  # SHA256 hex digest
sin_encrypted: LargeBinary + NotNull  # AES-256-GCM encrypted
dob_encrypted: LargeBinary + NotNull  # AES-256-GCM encrypted
employment_type: Enum(salaried, self-employed, contract) + NotNull
gross_annual_income: Decimal(12,2) + NotNull + Check > 0
credit_score: Integer + Check between 300-900 + Nullable
created_at: DateTime + NotNull + default now()

# Index for FINTRAC lookup
Index('idx_borrower_sin_hash', sin_hash)
```

#### `orchestrator_documents`
```python
__tablename__ = "orchestrator_documents"

id: UUID(pk)
application_id: UUID(FK→orchestrator_applications.id, index)
document_type: Enum(paystub, t4, notice_of_assessment, bank_statement, property_appraisal) + NotNull
file_name: String(255) + NotNull
s3_bucket: String(100) + NotNull
s3_key: String(500) + NotNull + Unique
file_size_bytes: Integer + NotNull
uploaded_at: DateTime + NotNull + default now()
processed_at: DateTime + Nullable
status: Enum(pending, processed, failed) + NotNull + Default pending
created_at: DateTime + NotNull + default now()

# Index for listing documents per application
Index('idx_docs_app_status', application_id, status)
```

#### `orchestrator_application_tasks`
Tracks Celery task execution for auditability.
```python
__tablename__ = "orchestrator_application_tasks"

id: UUID(pk)
application_id: UUID(FK→orchestrator_applications.id, index)
task_name: Enum(extract_documents, evaluate_policy, run_decision) + NotNull
celery_task_id: String(155) + Unique + Nullable
status: Enum(pending, running, success, failed, retrying) + NotNull
retry_count: Integer + Default 0 + NotNull
result_data: JSONB + Nullable  # Store task results
error_message: Text + Nullable
started_at: DateTime + Nullable
completed_at: DateTime + Nullable
created_at: DateTime + NotNull + default now()
updated_at: DateTime + NotNull + default now() + onupdate now()

# Index for task status monitoring
Index('idx_tasks_app_task', application_id, task_name)
Index('idx_tasks_celery_id', celery_task_id)
```

#### `orchestrator_fintrac_verifications`
Immutable FINTRAC identity verification log.
```python
__tablename__ = "orchestrator_fintrac_verifications"

id: UUID(pk)
application_id: UUID(FK→orchestrator_applications.id, index)
verification_method: Enum(documentary, electronic, dual_process) + NotNull
verification_result: Enum(passed, failed) + NotNull
verified_by: String(50) + NotNull  # Employee ID
notes: Text + Nullable
verified_at: DateTime + NotNull + default now()
created_at: DateTime + NotNull + default now()

# FINTRAC 5-year retention compliance: records never updated or deleted
# Index for compliance reporting
Index('idx_fintrac_app_method', application_id, verification_method)
```

#### `orchestrator_fintrac_reports`
FINTRAC Large Cash Transaction Reports (LCTR).
```python
__tablename__ = "orchestrator_fintrac_reports"

id: UUID(pk)
application_id: UUID(FK→orchestrator_applications.id, index)
fntrac_report_id: String(100) + Unique + NotNull  # Generated FINTRAC reference
transaction_amount: Decimal(12,2) + NotNull + Check > 0
transaction_type: Enum(purchase, refinance, renewal) + NotNull
threshold_exceeded: Boolean + Computed(transaction_amount > 10000)
funds_source: Text + Nullable  # Required if threshold_exceeded
third_party_involved: Boolean + Nullable  # Required if threshold_exceeded
reported_at: DateTime + NotNull + default now()
created_at: DateTime + NotNull + default now()

# Index for threshold monitoring
Index('idx_fintrac_threshold', threshold_exceeded, reported_at.desc())
```

#### `orchestrator_audit_log`
Immutable audit trail for all state changes (FINTRAC compliance).
```python
__tablename__ = "orchestrator_audit_log"

id: UUID(pk)
application_id: UUID(FK→orchestrator_applications.id, index)
action: String(50) + NotNull  # e.g., 'status_change', 'decision_made'
actor_id: UUID + NotNull  # User ID
actor_role: String(50) + NotNull  # Role name
old_value: JSONB + Nullable
new_value: JSONB + NotNull
ip_address: INET + Nullable
created_at: DateTime + NotNull + default now()

# Composite index for audit queries
Index('idx_audit_app_action', application_id, action)
Index('idx_audit_actor', actor_id, created_at.desc())
```

---

## 3. Business Logic

### 3.1 State Machine

```python
ApplicationStatus = {
    "submitted": "Initial state, documents uploaded",
    "extracting": "Celery task extract_documents running",
    "evaluating": "Celery task evaluate_policy running",
    "decided": "Celery task run_decision completed",
    "exception": "Processing failed after max retries"
}

DecisionStatus = {
    "approved": "Meets all lender and regulatory criteria",
    "rejected": "Fails GDS/TDS, credit, or policy rules",
    "pending": "Awaiting manual underwriter review",
    "exception": "System error or missing data"
}

# State transitions (valid):
submitted → extracting → evaluating → decided → (approved|rejected|pending)
Any state → exception (on unrecoverable error)
exception → submitted (via reprocess endpoint, admin only)
```

### 3.2 Celery Task Orchestration

**Task Flow**: `extract_documents` → `evaluate_policy` → `run_decision`

#### Task 1: `extract_documents`
- **Timeout**: 5 minutes
- **Retry**: 3 attempts, exponential backoff (2^retry_count seconds)
- **Logic**:
  1. Fetch document records for application
  2. Download PDFs from MinIO/S3
  3. Call document_extraction service (gRPC/HTTP)
  4. Parse extracted data (income, employment, assets)
  5. Update `orchestrator_borrowers` with extracted values
  6. Update document status to 'processed'
  7. Transition application status to 'evaluating'
  8. Trigger `evaluate_policy` task

**Failure Handling**: If all retries exhausted → mark application as 'exception', log error in `application_tasks`, notify admin via structlog.

#### Task 2: `evaluate_policy`
- **Timeout**: 3 minutes
- **Retry**: 3 attempts
- **Logic**:
  1. Fetch application and borrower data
  2. **OSFI B-20 Stress Test**:
     ```python
     contract_rate = get_lender_rate(lender_id)
     qualifying_rate = max(contract_rate + Decimal('2.00'), Decimal('5.25'))
     ```
  3. **GDS Calculation**:
     ```python
     # PITH = Principal + Interest + Taxes + Heating
     monthly_mortgage = calculate_payment(mortgage_amount, qualifying_rate)
     monthly_taxes = estimate_property_taxes(property_value)
     monthly_heating = estimate_heating_cost(property_value)
     gds_ratio = (monthly_mortgage + monthly_taxes + monthly_heating) / (gross_annual_income / 12)
     ```
  4. **TDS Calculation**:
     ```python
     # Include other debts from credit report
     other_debts = fetch_credit_obligations(borrower_id)
     tds_ratio = (monthly_mortgage + monthly_taxes + monthly_heating + other_debts) / (gross_annual_income / 12)
     ```
  5. **CMHC Insurance Check**:
     ```python
     ltv_ratio = mortgage_amount / property_value
     insurance_required = ltv_ratio > Decimal('0.80')
     if insurance_required:
         insurance_premium = calculate_cmhc_premium(ltv_ratio, mortgage_amount)
     ```
  6. **Policy Rules Validation**:
     - GDS ≤ 39% (hard limit)
     - TDS ≤ 44% (hard limit)
     - Credit score ≥ lender minimum (typically 600)
     - LTV ≤ lender maximum (typically 95%)
  7. Store ratios and qualifying_rate in `orchestrator_applications`
  8. Log full calculation breakdown to `audit_log` (PII-excluded)
  9. Transition to 'decided' and trigger `run_decision` task

**Failure Handling**: If ratio calculation fails → log error, mark as 'exception'. If policy service unreachable → retry with backoff.

#### Task 3: `run_decision`
- **Timeout**: 2 minutes
- **Retry**: 2 attempts (less critical, mostly DB updates)
- **Logic**:
  1. Evaluate policy rule results
  2. Apply lender-specific overrides
  3. Determine final decision:
     - `approved`: All rules pass, GDS/TDS within limits, no exceptions
     - `rejected`: GDS/TDS exceed limits, or critical policy failure
     - `pending`: Manual review required (borderline ratios, exceptions)
  4. Update `decision` and `decision_reason` fields
  5. If transaction_amount > $10,000, create `fintrac_reports` record automatically
  6. Log decision to `audit_log`

### 3.3 Retry & Timeout Configuration

```python
# Celery task settings (common/config.py)
CELERY_TASK_CONFIG = {
    "extract_documents": {
        "soft_timeout": 300,  # 5 min
        "hard_timeout": 330,
        "max_retries": 3,
        "retry_backoff": True,
        "retry_backoff_max": 600,  # 10 min
        "retry_jitter": True
    },
    "evaluate_policy": {
        "soft_timeout": 180,  # 3 min
        "hard_timeout": 210,
        "max_retries": 3,
        "retry_backoff": True,
        "retry_backoff_max": 300
    },
    "run_decision": {
        "soft_timeout": 120,  # 2 min
        "hard_timeout": 150,
        "max_retries": 2,
        "retry_backoff": False  # Fast fail for decision
    }
}

# Timeout triggers structlog warning + OpenTelemetry span event
# Hard timeout kills worker process and marks task as failed
```

### 3.4 Reprocessing Logic

- **Allowed States**: 'decided', 'exception' only
- **Preserve Documents**: If true, reuse existing S3 objects; if false, require new upload
- **Audit Trail**: Reprocess action logged with reason in `audit_log`
- **State Reset**: Clears previous decision, ratios, and task history; resets to 'submitted'

---

## 4. Migrations

### 4.1 New Tables

```sql
-- migration: 2024_01_create_orchestrator_tables
CREATE TABLE orchestrator_borrowers (
    id UUID PRIMARY KEY,
    full_name VARCHAR(200) NOT NULL,
    sin_hash VARCHAR(64) NOT NULL UNIQUE,
    sin_encrypted BYTEA NOT NULL,
    dob_encrypted BYTEA NOT NULL,
    employment_type VARCHAR(20) NOT NULL CHECK (employment_type IN ('salaried', 'self-employed', 'contract')),
    gross_annual_income DECIMAL(12,2) NOT NULL CHECK (gross_annual_income > 0),
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE orchestrator_applications (
    id UUID PRIMARY KEY,
    borrower_id UUID NOT NULL REFERENCES orchestrator_borrowers(id),
    lender_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('submitted', 'extracting', 'evaluating', 'decided', 'exception')),
    property_value DECIMAL(12,2) NOT NULL CHECK (property_value > 0),
    purchase_price DECIMAL(12,2) NOT NULL CHECK (purchase_price > 0),
    mortgage_amount DECIMAL(12,2) NOT NULL CHECK (mortgage_amount > 0),
    ltv_ratio DECIMAL(5,4) GENERATED ALWAYS AS (mortgage_amount / property_value) STORED,
    insurance_required BOOLEAN NOT NULL DEFAULT FALSE,
    insurance_premium DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    gds_ratio DECIMAL(5,4),
    tds_ratio DECIMAL(5,4),
    qualifying_rate DECIMAL(5,4),
    decision VARCHAR(20) CHECK (decision IN ('approved', 'rejected', 'pending', 'exception')),
    decision_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE orchestrator_documents (...);  -- See model definition
CREATE TABLE orchestrator_application_tasks (...);
CREATE TABLE orchestrator_fintrac_verifications (...);
CREATE TABLE orchestrator_fintrac_reports (...);
CREATE TABLE orchestrator_audit_log (...);
```

### 4.2 Indexes

```sql
CREATE INDEX idx_app_borrower_status ON orchestrator_applications(borrower_id, status);
CREATE INDEX idx_app_lender_decision ON orchestrator_applications(lender_id, decision);
CREATE INDEX idx_app_status_created ON orchestrator_applications(status, created_at DESC);
CREATE INDEX idx_borrower_sin_hash ON orchestrator_borrowers(sin_hash);
CREATE INDEX idx_docs_app_status ON orchestrator_documents(application_id, status);
CREATE INDEX idx_fintrac_threshold ON orchestrator_fintrac_reports(threshold_exceeded, reported_at DESC);
CREATE INDEX idx_audit_app_action ON orchestrator_audit_log(application_id, action);
```

### 4.3 Data Migration

- **None required** for new module. Seed `lenders` table with lender_id references if not already present.

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Compliance

- **Stress Test Enforcement**: `evaluate_policy` task **must** calculate `qualifying_rate = max(contract_rate + 2%, 5.25%)` using Decimal arithmetic.
- **Hard Limits**: GDS ≤ 39%, TDS ≤ 44%. If exceeded, decision **must** be 'rejected'.
- **Auditability**: Every ratio calculation logged to `orchestrator_audit_log` with:
  ```json
  {
    "action": "ratio_calculated",
    "new_value": {
      "gds_ratio": "0.3512",
      "tds_ratio": "0.4234",
      "qualifying_rate": "0.0725",
      "monthly_income": "8333.33",
      "pith_breakdown": {"principal": "1200.00", "interest": "1800.00", "taxes": "400.00", "heating": "150.00"}
    }
  }
  ```
- **No Precision Loss**: All financial values use `Decimal(12,2)` or `Decimal(5,4)` for ratios.

### 5.2 FINTRAC Compliance

- **Immutable Records**: `orchestrator_fintrac_verifications` and `orchestrator_fintrac_reports` have **no UPDATE/DELETE** operations. Implement DB-level triggers to prevent modifications.
- **Identity Verification**: `POST /verify-identity` **must** be called for every application before decision. Verification method and result are permanently logged.
- **Transaction Reporting**: Automatic report generation when `mortgage_amount ≥ $10,000`. `threshold_exceeded` flag set via computed column.
- **5-Year Retention**: All FINTRAC tables include `created_at`. Implement data retention policy: soft-delete/archive after 5 years to cold storage (S3 Glacier).
- **Audit Trail**: `orchestrator_audit_log` captures all actions with `actor_id` and `ip_address` for FINTRAC examination readiness.

### 5.3 CMHC Insurance Logic

- **LTV Calculation**: `ltv_ratio = mortgage_amount / property_value` (Decimal division).
- **Insurance Requirement**: If `ltv_ratio > 0.80`, set `insurance_required = True`.
- **Premium Tiers** (lookup in `evaluate_policy`):
  ```python
  if Decimal('0.8001') <= ltv <= Decimal('0.85'): premium_rate = Decimal('0.0280')
  elif Decimal('0.8501') <= ltv <= Decimal('0.90'): premium_rate = Decimal('0.0310')
  elif Decimal('0.9001') <= ltv <= Decimal('0.95'): premium_rate = Decimal('0.0400')
  insurance_premium = mortgage_amount * premium_rate
  ```

### 5.4 PIPEDA Data Handling

- **Encryption at Rest**: 
  - `sin_encrypted`: AES-256-GCM encrypted raw SIN (9 digits)
  - `dob_encrypted`: AES-256-GCM encrypted date of birth
  - Encryption keys managed via `common/security.encrypt_pii()` using envelope encryption with AWS KMS/Azure Key Vault
- **Hashing for Lookups**: `sin_hash = SHA256(sin)` used for duplicate checks, **never** for authentication.
- **Data Minimization**: API responses **exclude** `sin_encrypted`, `dob_encrypted`, `sin_hash`. Only return `full_name`, `employment_type`, `gross_annual_income`, `credit_score`.
- **No Logging PII**: structlog configuration **must** filter out `sin`, `dob`, `income` from logs. Use `logger.bind(sin_hash=<hash>)` for correlation.
- **Access Control**: `@require_roles('underwriter', 'admin')` on endpoints that expose sensitive data.

### 5.5 Authentication & Authorization

- **FastAPI Dependencies**:
  ```python
  async def get_current_user(token: JWT) → User
  async def require_underwriter(user: User) → User  # Raises 403
  async def require_admin(user: User) → User  # Raises 403
  ```
- **mTLS**: Internal service-to-service calls (e.g., to document_extraction) use mutual TLS via `common/security.verify_mtls()`.
- **Rate Limiting**: `POST /applications` limited to 10 requests/minute per user to prevent spam.

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy

```python
# modules/orchestrator/exceptions.py
class OrchestratorException(AppException):
    """Base for all orchestrator errors"""
    module_code = "ORCHESTRATOR"

class ApplicationNotFoundError(OrchestratorException):
    http_status = 404
    error_code = "ORCHESTRATOR_001"
    message_template = "Application {application_id} not found"

class ApplicationValidationError(OrchestratorException):
    http_status = 422
    error_code = "ORCHESTRATOR_002"
    message_template = "{field}: {reason}"

class ApplicationBusinessRuleError(OrchestratorException):
    http_status = 409
    error_code = "ORCHESTRATOR_003"
    message_template = "Business rule violated: {rule} - {detail}"

class DocumentUploadError(OrchestratorException):
    http_status = 400
    error_code = "ORCHESTRATOR_004"
    message_template = "Document upload failed: {reason}"

class TaskProcessingError(OrchestratorException):
    http_status = 500
    error_code = "ORCHESTRATOR_005"
    message_template = "Async task {task_name} failed after {retry_count} retries"

class FintracVerificationError(OrchestratorException):
    http_status = 422
    error_code = "ORCHESTRATOR_006"
    message_template = "FINTRAC verification error: {detail}"

class FintracReportError(OrchestratorException):
    http_status = 400
    error_code = "ORCHESTRATOR_007"
    message_template = "FINTRAC report requirement: {detail}"
```

### 6.2 Error Response Format

All errors return consistent JSON:
```json
{
  "detail": "Application 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "ORCHESTRATOR_001",
  "timestamp": "2024-01-15T14:30:00Z",
  "correlation_id": "req-abc123",
  "module": "orchestrator"
}
```

### 6.3 Global Exception Handlers (FastAPI)

```python
# modules/orchestrator/routes.py or common/exceptions.py
@app.exception_handler(OrchestratorException)
async def orchestrator_exception_handler(request, exc):
    logger.error(
        "orchestrator.error",
        error_code=exc.error_code,
        correlation_id=request.state.correlation_id,
        application_id=exc.context.get("application_id")
        # No PII logged
    )
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": request.state.correlation_id,
            "module": "orchestrator"
        }
    )
```

### 6.4 Retry & Circuit Breaker Integration

- **Celery Retry**: Automatic via `self.retry()` in task classes.
- **Circuit Breaker**: For external services (document extraction, credit bureau), use `pybreaker` with 5 failures threshold, 60s recovery.
- **Dead Letter Queue**: Failed tasks after max retries routed to `orchestrator-dlq` queue for manual inspection.

---

## 7. Observability & Monitoring (Supplementary)

### 7.1 Logging

```python
# In services.py
logger = structlog.get_logger("orchestrator")

async def submit_application(...):
    logger.info(
        "application.submitted",
        application_id=str(app.id),
        lender_id=str(lender_id),
        ltv_ratio=str(ltv),
        correlation_id=correlation_id
        # No PII
    )
```

### 7.2 Metrics (Prometheus)

```python
# Exposed at /metrics
orchestrator_applications_total{status="submitted"} 42
orchestrator_tasks_failed_total{task_name="extract_documents"} 3
orchestrator_fintrac_reports_total{threshold_exceeded="true"} 15
orchestrator_decision_ratio_gds{decision="rejected"} 0.4521
```

### 7.3 Health Checks

```python
# GET /health
{
  "status": "healthy",
  "services": {
    "postgres": "ok",
    "minio": "ok",
    "celery": "ok",
    "redis": "ok"
  },
  "version": "1.0.0"
}
```

---

**End of Design Plan**