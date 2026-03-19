# Orchestrator Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Orchestrator Service Design Plan

**File:** `docs/design/orchestrator-service.md`

---

## 1. Endpoints

### 1.1 Application Management

#### `POST /api/v1/applications`
Submit a new mortgage application with PDF documents.

**Authentication:** Authenticated (lender or broker JWT)

**Request Body (multipart/form-data):**
```json
{
  "lender_id": "uuid (required)",
  "borrower": {
    "full_name": "str (required, max 255)",
    "sin": "str (required, 9 digits, encrypted)",
    "date_of_birth": "date (required)",
    "employment_type": "enum[salaried, self-employed, contract] (required)",
    "gross_annual_income": "Decimal (required, >= 0)",
    "credit_score": "int (optional, 300-900)"
  },
  "property_value": "Decimal (required, > 0)",
  "purchase_price": "Decimal (required, > 0)",
  "mortgage_amount": "Decimal (required, > 0)",
  "property_address": "str (required)",
  "documents": "List[UploadFile] (required, min 1, max 10, PDF only, max 10MB each)"
}
```

**Response (201 Created):**
```json
{
  "application_id": "uuid",
  "status": "submitted",
  "created_at": "datetime (ISO8601)",
  "message": "Application submitted successfully. Processing initiated."
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | ORCHESTRATOR_002 | Invalid file type (non-PDF) or size > 10MB |
| 422 | ORCHESTRATOR_002 | Invalid SIN format, negative income, or missing required fields |
| 422 | ORCHESTRATOR_003 | Mortgage amount > purchase_price (LTV > 100%) |
| 401 | AUTH_001 | Missing or invalid JWT token |
| 403 | AUTH_002 | Insufficient permissions (non-lender/broker role) |

---

#### `GET /api/v1/applications/{id}`
Retrieve application status, decision, and audit trail.

**Authentication:** Authenticated (lender, broker, or admin JWT)

**Response (200 OK):**
```json
{
  "application_id": "uuid",
  "status": "enum[submitted, extracting, evaluating, decided, exception]",
  "borrower": {
    "full_name": "str",
    "employment_type": "enum",
    "gross_annual_income": "Decimal",
    "credit_score": "int"
  },
  "property_value": "Decimal",
  "purchase_price": "Decimal",
  "mortgage_amount": "Decimal",
  "ltv_ratio": "Decimal (4 precision)",
  "cmhc_insurance_required": "bool",
  "cmhc_premium": "Decimal (nullable)",
  "gds_ratio": "Decimal (4 precision, nullable)",
  "tds_ratio": "Decimal (4 precision, nullable)",
  "qualifying_rate": "Decimal (4 precision, nullable)",
  "decision": "enum[approved, rejected, referred, pending] (nullable)",
  "decision_reason": "str (nullable)",
  "created_at": "datetime",
  "updated_at": "datetime",
  "processing_started_at": "datetime (nullable)",
  "decision_made_at": "datetime (nullable)"
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | ORCHESTRATOR_001 | Application ID not found |
| 401 | AUTH_001 | Missing or invalid JWT token |
| 403 | AUTH_002 | User does not own this application |

---

#### `GET /api/v1/applications/{id}/documents`
List all uploaded documents for an application.

**Authentication:** Authenticated (lender, broker, or admin JWT)

**Response (200 OK):**
```json
{
  "application_id": "uuid",
  "documents": [
    {
      "document_id": "uuid",
      "filename": "str",
      "minio_path": "str (internal)",
      "uploaded_at": "datetime",
      "extraction_status": "enum[pending, processing, completed, failed]",
      "extracted_data": "object (nullable)"
    }
  ]
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | ORCHESTRATOR_001 | Application ID not found |
| 401 | AUTH_001 | Missing or invalid JWT token |

---

#### `POST /api/v1/applications/{id}/reprocess`
Trigger reprocessing of an application in `exception` or `decided` status.

**Authentication:** Authenticated (admin or lender with `reprocess` permission)

**Response (202 Accepted):**
```json
{
  "application_id": "uuid",
  "old_status": "exception",
  "new_status": "submitted",
  "reprocess_reason": "str (from request body)",
  "reprocessed_at": "datetime"
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | ORCHESTRATOR_003 | Application not in reprocessable status (e.g., `evaluating`) |
| 404 | ORCHESTRATOR_001 | Application ID not found |
| 401 | AUTH_001 | Missing or invalid JWT token |
| 403 | AUTH_002 | Insufficient permissions |

---

#### `GET /api/v1/applications`
List applications with pagination and filtering.

**Authentication:** Authenticated (lender, broker, or admin JWT)

**Query Parameters:**
- `page`: int (default: 1)
- `limit`: int (default: 20, max: 100)
- `status`: enum (optional, filter)
- `lender_id`: uuid (optional, admin only)
- `borrower_sin_hash`: str (optional, exact match, admin only)

**Response (200 OK):**
```json
{
  "total": "int",
  "page": "int",
  "limit": "int",
  "applications": [
    {
      "application_id": "uuid",
      "status": "enum",
      "borrower_name": "str",
      "mortgage_amount": "Decimal",
      "created_at": "datetime"
    }
  ]
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 422 | ORCHESTRATOR_002 | Invalid pagination parameters |
| 401 | AUTH_001 | Missing or invalid JWT token |

---

### 1.2 FINTRAC Compliance

#### `POST /api/v1/fintrac/applications/{id}/verify-identity`
Log identity verification attempt (mandatory for all applications).

**Authentication:** Authenticated (lender JWT)

**Request Body:**
```json
{
  "verification_method": "enum[document, electronic, credit_bureau] (required)",
  "verified_by": "str (required, employee ID)",
  "verification_timestamp": "datetime (required)"
}
```

**Response (201 Created):**
```json
{
  "verification_id": "uuid",
  "application_id": "uuid",
  "status": "verified",
  "created_at": "datetime",
  "fintrac_record_id": "str (internal audit trail ID)"
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | ORCHESTRATOR_001 | Application ID not found |
| 409 | FINTRAC_001 | Identity verification already recorded |
| 422 | ORCHESTRATOR_002 | Invalid verification method |
| 401 | AUTH_001 | Missing or invalid JWT token |

---

#### `GET /api/v1/fintrac/applications/{id}/verification`
Get FINTRAC identity verification status.

**Authentication:** Authenticated (lender or admin JWT)

**Response (200 OK):**
```json
{
  "application_id": "uuid",
  "verification_status": "enum[not_started, pending, verified, failed]",
  "verification_method": "str (nullable)",
  "verified_at": "datetime (nullable)",
  "fintrac_record_id": "str (nullable)",
  "retention_until": "datetime (+5 years from verification)"
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | ORCHESTRATOR_001 | Application ID not found |
| 401 | AUTH_001 | Missing or invalid JWT token |

---

#### `POST /api/v1/fintrac/applications/{id}/report-transaction`
File FINTRAC report for transactions > CAD $10,000.

**Authentication:** Authenticated (lender JWT with `fintrac_reporting` role)

**Request Body:**
```json
{
  "transaction_type": "enum[purchase, refinance, renewal] (required)",
  "transaction_amount": "Decimal (required, >= 10000.00)",
  "transaction_date": "date (required)",
  "funds_source": "str (required, 255 chars)",
  "third_party_involved": "bool (required)"
}
```

**Response (202 Accepted):**
```json
{
  "report_id": "uuid",
  "fintrac_filing_id": "str (government confirmation ID)",
  "status": "filed",
  "filed_at": "datetime"
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | FINTRAC_002 | Transaction amount < $10,000 CAD (not reportable) |
| 404 | ORCHESTRATOR_001 | Application ID not found |
| 409 | FINTRAC_003 | Report already filed for this application |
| 422 | ORCHESTRATOR_002 | Invalid transaction type or amount format |
| 401 | AUTH_001 | Missing or invalid JWT token |
| 403 | AUTH_002 | Missing `fintrac_reporting` permission |

---

#### `GET /api/v1/fintrac/risk-assessment/{client_id}`
Get aggregated risk assessment for a client across all applications.

**Authentication:** Authenticated (admin JWT only)

**Response (200 OK):**
```json
{
  "client_id": "uuid (hashed SIN-based)",
  "total_applications": "int",
  "total_transaction_value": "Decimal",
  "fintrac_reports_count": "int",
  "risk_score": "int (0-100, algorithmic)",
  "flags": "List[str] (e.g., ['high_frequency', 'large_cash'])",
  "last_activity": "datetime"
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | FINTRAC_004 | Client ID not found |
| 401 | AUTH_001 | Missing or invalid JWT token |
| 403 | AUTH_002 | Admin access only |

---

## 2. Models & Database

### 2.1 Core Models

#### `applications` Table
```python
Table: applications

Columns:
  id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
  borrower_id: UUID NOT NULL FOREIGN KEY borrowers.id
  lender_id: UUID NOT NULL FOREIGN KEY lenders.id (from common module)
  status: VARCHAR(20) NOT NULL CHECK (status IN ('submitted', 'extracting', 'evaluating', 'decided', 'exception'))
  
  # Financial fields (Decimal, precision=15, scale=4)
  property_value: DECIMAL(15,4) NOT NULL CHECK (property_value > 0)
  purchase_price: DECIMAL(15,4) NOT NULL CHECK (purchase_price > 0)
  mortgage_amount: DECIMAL(15,4) NOT NULL CHECK (mortgage_amount > 0)
  
  # Calculated fields
  ltv_ratio: DECIMAL(5,4) GENERATED ALWAYS AS (mortgage_amount / property_value) STORED
  cmhc_insurance_required: BOOLEAN GENERATED ALWAYS AS (ltv_ratio > 0.80) STORED
  cmhc_premium: DECIMAL(15,4) NULL
  
  # OSFI B-20 Ratios (nullable until calculated)
  gds_ratio: DECIMAL(5,4) NULL CHECK (gds_ratio >= 0)
  tds_ratio: DECIMAL(5,4) NULL CHECK (tds_ratio >= 0)
  qualifying_rate: DECIMAL(5,4) NULL CHECK (qualifying_rate >= 0)
  
  # Decision
  decision: VARCHAR(20) NULL CHECK (decision IN ('approved', 'rejected', 'referred', 'pending'))
  decision_reason: TEXT NULL
  
  # Audit (mandatory)
  created_at: TIMESTAMP NOT NULL DEFAULT NOW()
  updated_at: TIMESTAMP NOT NULL DEFAULT NOW()
  processing_started_at: TIMESTAMP NULL
  decision_made_at: TIMESTAMP NULL
  created_by: UUID NOT NULL (user ID from JWT)

Indexes:
  - INDEX idx_applications_status ON applications(status)
  - INDEX idx_applications_lender_id ON applications(lender_id)
  - INDEX idx_applications_borrower_id ON applications(borrower_id)
  - INDEX idx_applications_created_at ON applications(created_at DESC)
  - COMPOSITE INDEX idx_applications_lender_status ON applications(lender_id, status)
```

#### `borrowers` Table
```python
Table: borrowers

Columns:
  id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
  
  # PII Fields (encrypted_at_rest)
  full_name: VARCHAR(255) NOT NULL ENCRYPTED
  encrypted_sin: BYTEA NOT NULL (AES-256 encrypted)
  sin_hash: VARCHAR(64) NOT NULL UNIQUE (SHA256 hex digest for lookups)
  date_of_birth: DATE NOT NULL ENCRYPTED
  
  # Financial profile
  employment_type: VARCHAR(20) NOT NULL CHECK (employment_type IN ('salaried', 'self-employed', 'contract'))
  gross_annual_income: DECIMAL(15,4) NOT NULL CHECK (gross_annual_income >= 0)
  credit_score: INTEGER NULL CHECK (credit_score BETWEEN 300 AND 900)
  
  # Audit (mandatory)
  created_at: TIMESTAMP NOT NULL DEFAULT NOW()
  created_by: UUID NOT NULL (user ID from JWT)

Indexes:
  - UNIQUE INDEX idx_borrowers_sin_hash ON borrowers(sin_hash)
  - INDEX idx_borrowers_created_at ON borrowers(created_at DESC)
```

#### `documents` Table
```python
Table: documents

Columns:
  id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
  application_id: UUID NOT NULL FOREIGN KEY applications.id ON DELETE CASCADE
  filename: VARCHAR(500) NOT NULL
  minio_bucket: VARCHAR(255) NOT NULL
  minio_object_key: VARCHAR(500) NOT NULL (path)
  file_size_bytes: BIGINT NOT NULL CHECK (file_size_bytes > 0)
  
  extraction_status: VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (extraction_status IN ('pending', 'processing', 'completed', 'failed'))
  extracted_data: JSONB NULL (parsed document data)
  extraction_error: TEXT NULL
  
  # Audit
  created_at: TIMESTAMP NOT NULL DEFAULT NOW()
  created_by: UUID NOT NULL

Indexes:
  - INDEX idx_documents_application_id ON documents(application_id)
  - INDEX idx_documents_extraction_status ON documents(extraction_status)
```

### 2.2 FINTRAC Compliance Models

#### `fintrac_verifications` Table
```python
Table: fintrac_verifications

Columns:
  id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
  application_id: UUID NOT NULL UNIQUE FOREIGN KEY applications.id
  verification_method: VARCHAR(30) NOT NULL CHECK (verification_method IN ('document', 'electronic', 'credit_bureau'))
  verified_by: UUID NOT NULL (employee ID)
  verification_timestamp: TIMESTAMP NOT NULL
  fintrac_record_id: VARCHAR(100) NOT NULL (internal audit ID)
  
  # Audit (immutable per FINTRAC)
  created_at: TIMESTAMP NOT NULL DEFAULT NOW()
  retention_until: TIMESTAMP GENERATED ALWAYS AS (created_at + INTERVAL '5 years') STORED

Indexes:
  - UNIQUE INDEX idx_fintrac_verifications_application ON fintrac_verifications(application_id)
  - INDEX idx_fintrac_verifications_record_id ON fintrac_verifications(fintrac_record_id)
  - INDEX idx_fintrac_retention ON fintrac_verifications(retention_until)
```

#### `fintrac_reports` Table
```python
Table: fintrac_reports

Columns:
  id: UUID PRIMARY KEY DEFAULT gen_random_uuid()
  application_id: UUID NOT NULL FOREIGN KEY applications.id
  transaction_type: VARCHAR(30) NOT NULL CHECK (transaction_type IN ('purchase', 'refinance', 'renewal'))
  transaction_amount: DECIMAL(15,4) NOT NULL CHECK (transaction_amount >= 10000.00)
  transaction_date: DATE NOT NULL
  funds_source: TEXT NOT NULL
  third_party_involved: BOOLEAN NOT NULL
  
  # Filing confirmation
  fintrac_filing_id: VARCHAR(100) NULL (government confirmation)
  filed_at: TIMESTAMP NULL
  
  # Audit (immutable)
  created_at: TIMESTAMP NOT NULL DEFAULT NOW()
  created_by: UUID NOT NULL
  retention_until: TIMESTAMP GENERATED ALWAYS AS (created_at + INTERVAL '5 years') STORED

Indexes:
  - UNIQUE INDEX idx_fintrac_reports_application ON fintrac_reports(application_id)
  - INDEX idx_fintrac_reports_filing_id ON fintrac_reports(fintrac_filing_id)
  - INDEX idx_fintrac_amount_threshold ON fintrac_reports(transaction_amount)
```

---

## 3. Business Logic

### 3.1 State Machine & Pipeline Flow

```mermaid
stateDiagram-v2
    [*] --> submitted: POST /applications
    submitted --> extracting: Celery task extract_documents
    extracting --> evaluating: On success
    extracting --> exception: On failure (max retries)
    evaluating --> decided: Celery task run_decision
    evaluating --> exception: On policy error
    decided --> [*]: Return result
    exception --> submitted: POST /reprocess (manual)
    
    note right of extracting: "Timeout: 5 min\nRetries: 3 (exponential backoff)"
    note right of evaluating: "Timeout: 3 min\nNo retries"
    note right of decided: "Stores GDS/TDS\ncalculations in audit log"
```

### 3.2 Celery Task Specifications

#### Task 1: `extract_documents`
- **Queue:** `document-processing`
- **Timeout:** 300 seconds
- **Retry Policy:** 3 attempts, exponential backoff (2^retry_count * 30s)
- **Dead Letter Queue:** `dlq-document-extraction`
- **Logic:**
  1. Download PDF from MinIO
  2. Call document-extraction microservice (gRPC)
  3. Parse response: income, employment, property details
  4. Update `documents.extraction_status` and `extracted_data`
  5. If all documents processed, transition `applications.status` → `evaluating`
  6. On failure: log to structlog with correlation_id, update status to `exception`

#### Task 2: `evaluate_policy`
- **Queue:** `policy-evaluation`
- **Timeout:** 180 seconds
- **Retry Policy:** No retries (fail fast)
- **Logic:**
  1. Fetch application and borrower data
  2. Call policy-engine service (REST) with lender_id and borrower profile
  3. Check: credit score minimum, income stability, employment type
  4. Return policy_violations: List[str] or empty list
  5. If violations exist, transition to `exception` with reason
  6. If passed, trigger `run_decision` task

#### Task 3: `run_decision`
- **Queue:** `decision-engine`
- **Timeout:** 120 seconds
- **Retry Policy:** 1 retry on timeout only
- **Logic:**
  1. **CMHC Calculation:**
     - LTV = mortgage_amount / property_value
     - If LTV > 0.80: insurance_required = True
     - Premium tier lookup:
       - 80.01-85%: 2.80%
       - 85.01-90%: 3.10%
       - 90.01-95%: 4.00%
     - premium = mortgage_amount * premium_rate
  
  2. **OSFI B-20 Stress Test:**
     - Get contract_rate from lender config
     - qualifying_rate = max(contract_rate + 2%, 5.25%)
     - Calculate GDS = (PITH) / gross_monthly_income
     - Calculate TDS = (PITH + other_debt) / gross_monthly_income
     - Enforce: GDS ≤ 39%, TDS ≤ 44%
     - Log calculation breakdown: `{correlation_id, application_id, gds, tds, qualifying_rate, timestamp}`
  
  3. **Decision Matrix:**
     - IF GDS > 39% OR TDS > 44%: decision = `rejected`, reason = "OSFI B-20 threshold exceeded"
     - ELIF LTV > 0.95: decision = `rejected`, reason = "LTV exceeds maximum"
     - ELIF policy_violations: decision = `referred`, reason = "Manual review required"
     - ELSE: decision = `approved`
  
  4. Update `applications` with ratios, decision, timestamps
  5. If mortgage_amount ≥ $10,000, trigger FINTRAC report task

### 3.3 Retry & Timeout Configuration

```python
# Celery Configuration (in common/config.py)
CELERY_TASK_CONFIG = {
    "extract_documents": {
        "soft_timeout": 300,
        "hard_timeout": 330,
        "max_retries": 3,
        "retry_backoff": True,
        "retry_backoff_max": 600,
        "acks_late": True,
        "dead_letter_queue": "dlq-document-extraction"
    },
    "evaluate_policy": {
        "soft_timeout": 180,
        "hard_timeout": 200,
        "max_retries": 0,
        "acks_late": True
    },
    "run_decision": {
        "soft_timeout": 120,
        "hard_timeout": 140,
        "max_retries": 1,
        "retry_on": ["TimeoutError"],
        "acks_late": True
    }
}
```

---

## 4. Migrations

### 4.1 New Tables & Types

```sql
-- Alembic migration: create_orchestrator_tables.py

# 1. Create ENUM types
CREATE TYPE application_status AS ENUM ('submitted', 'extracting', 'evaluating', 'decided', 'exception');
CREATE TYPE employment_type AS ENUM ('salaried', 'self-employed', 'contract');
CREATE TYPE verification_method AS ENUM ('document', 'electronic', 'credit_bureau');
CREATE TYPE transaction_type AS ENUM ('purchase', 'refinance', 'renewal');
CREATE TYPE decision_outcome AS ENUM ('approved', 'rejected', 'referred', 'pending');

# 2. Create borrowers table
CREATE TABLE borrowers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) NOT NULL,
    encrypted_sin BYTEA NOT NULL,
    sin_hash VARCHAR(64) NOT NULL UNIQUE,
    date_of_birth DATE NOT NULL,
    employment_type employment_type NOT NULL,
    gross_annual_income DECIMAL(15,4) NOT NULL,
    credit_score INTEGER CHECK (credit_score BETWEEN 300 AND 900),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by UUID NOT NULL
);

# 3. Create applications table
CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    borrower_id UUID NOT NULL REFERENCES borrowers(id),
    lender_id UUID NOT NULL,
    status application_status NOT NULL,
    property_value DECIMAL(15,4) NOT NULL,
    purchase_price DECIMAL(15,4) NOT NULL,
    mortgage_amount DECIMAL(15,4) NOT NULL,
    ltv_ratio DECIMAL(5,4) GENERATED ALWAYS AS (mortgage_amount / property_value) STORED,
    cmhc_insurance_required BOOLEAN GENERATED ALWAYS AS (ltv_ratio > 0.80) STORED,
    cmhc_premium DECIMAL(15,4),
    gds_ratio DECIMAL(5,4),
    tds_ratio DECIMAL(5,4),
    qualifying_rate DECIMAL(5,4),
    decision decision_outcome,
    decision_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    processing_started_at TIMESTAMP,
    decision_made_at TIMESTAMP,
    created_by UUID NOT NULL
);

# 4. Create documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    minio_bucket VARCHAR(255) NOT NULL,
    minio_object_key VARCHAR(500) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    extraction_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    extracted_data JSONB,
    extraction_error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by UUID NOT NULL
);

# 5. Create fintrac_verifications table
CREATE TABLE fintrac_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL UNIQUE REFERENCES applications(id),
    verification_method verification_method NOT NULL,
    verified_by UUID NOT NULL,
    verification_timestamp TIMESTAMP NOT NULL,
    fintrac_record_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    retention_until TIMESTAMP GENERATED ALWAYS AS (created_at + INTERVAL '5 years') STORED
);

# 6. Create fintrac_reports table
CREATE TABLE fintrac_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id),
    transaction_type transaction_type NOT NULL,
    transaction_amount DECIMAL(15,4) NOT NULL,
    transaction_date DATE NOT NULL,
    funds_source TEXT NOT NULL,
    third_party_involved BOOLEAN NOT NULL,
    fintrac_filing_id VARCHAR(100),
    filed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by UUID NOT NULL,
    retention_until TIMESTAMP GENERATED ALWAYS AS (created_at + INTERVAL '5 years') STORED
);
```

### 4.2 Indexes

```sql
# Performance indexes
CREATE INDEX idx_applications_status ON applications(status);
CREATE INDEX idx_applications_lender_id ON applications(lender_id);
CREATE INDEX idx_applications_borrower_id ON applications(borrower_id);
CREATE INDEX idx_applications_created_at ON applications(created_at DESC);
CREATE INDEX idx_applications_lender_status ON applications(lender_id, status);
CREATE INDEX idx_applications_ltv ON applications(ltv_ratio);

CREATE UNIQUE INDEX idx_borrowers_sin_hash ON borrowers(sin_hash);
CREATE INDEX idx_borrowers_created_at ON borrowers(created_at DESC);

CREATE INDEX idx_documents_application_id ON documents(application_id);
CREATE INDEX idx_documents_extraction_status ON documents(extraction_status);

CREATE UNIQUE INDEX idx_fintrac_verifications_application ON fintrac_verifications(application_id);
CREATE INDEX idx_fintrac_verifications_record_id ON fintrac_verifications(fintrac_record_id);
CREATE INDEX idx_fintrac_retention ON fintrac_verifications(retention_until);

CREATE UNIQUE INDEX idx_fintrac_reports_application ON fintrac_reports(application_id);
CREATE INDEX idx_fintrac_reports_filing_id ON fintrac_reports(fintrac_filing_id);
CREATE INDEX idx_fintrac_amount_threshold ON fintrac_reports(transaction_amount);
```

---

## 5. Security & Compliance

### 5.1 PIPEDA (Data Protection)

**Encryption at Rest:**
- `borrowers.encrypted_sin`: AES-256-GCM encrypted (key from Vault)
- `borrowers.full_name`: AES-256-CBC encrypted
- `borrowers.date_of_birth`: AES-256-CBC encrypted
- Encryption/decryption handled in `common/security.py:encrypt_pii()` / `decrypt_pii()`
- SIN hash used for all lookups; raw SIN never logged or returned in APIs

**Data Minimization:**
- Only collect fields required for underwriting (no middle names, no SIN history)
- Auto-purge temporary files from MinIO after 30 days (configurable)

### 5.2 OSFI B-20 (Stress Test & Ratios)

**Mandatory Calculations:**
- Qualifying rate: `max(contract_rate + 2%, 5.25%)` - logged with correlation_id
- GDS/TDS must be calculated for every decision
- Hard limits enforced: GDS ≤ 39%, TDS ≤ 44%
- Audit trail: All ratio calculations stored in `applications` table and logged to `decision_audit_log` table (append-only)

**Audit Logging:**
```json
{
  "event": "osfi_b20_calculation",
  "correlation_id": "uuid",
  "application_id": "uuid",
  "gds_ratio": 0.3875,
  "tds_ratio": 0.4210,
  "qualifying_rate": 0.0725,
  "contract_rate": 0.0525,
  "gross_monthly_income": 8500.00,
  "pith_amount": 3293.75,
  "other_debt": 250.00,
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### 5.3 FINTRAC (Transaction Reporting)

**Identity Verification:**
- Must be logged before decision is finalized
- `fintrac_verifications` table is immutable (no UPDATE/DELETE)
- Retention: 5 years automatic via `retention_until` column

**Large Transaction Reporting:**
- Automatic trigger when `mortgage_amount ≥ 10000.00`
- Report must be filed within 15 days of transaction
- `fintrac_reports` table is immutable; `filed_at` set only after government confirmation
- Dead letter queue for failed filings: `dlq-fintrac-reporting`

**Risk Assessment:**
- Aggregates data across applications using `sin_hash` as client identifier
- Flags: >3 applications/year, >$500k total, frequent cash sources

### 5.4 Authentication & Authorization

**JWT Claims Required:**
- `sub`: user_id (UUID)
- `role`: enum[lender, broker, admin]
- `lender_id`: UUID (for lender-scoped access)
- `permissions`: List[str] (e.g., `["applications:read", "applications:write", "fintrac:report"]`)

**mTLS:**
- Service-to-service communication (Celery workers → microservices) uses mTLS
- Certificates managed by Vault PKI, rotated every 7 days

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy

```python
# In modules/orchestrator/exceptions.py

class OrchestratorException(AppException):
    """Base exception for orchestrator module"""
    module_code = "ORCHESTRATOR"

class ApplicationNotFoundError(OrchestratorException):
    """Raised when application ID does not exist"""
    http_status = 404
    error_code = "ORCHESTRATOR_001"
    message_pattern = "Application {application_id} not found"

class ApplicationValidationError(OrchestratorException):
    """Raised on input validation failures"""
    http_status = 422
    error_code = "ORCHESTRATOR_002"
    message_pattern = "{field}: {reason}"

class ApplicationBusinessRuleError(OrchestratorException):
    """Raised when business rules are violated (e.g., LTV > 100%)"""
    http_status = 409
    error_code = "ORCHESTRATOR_003"
    message_pattern = "Business rule violated: {rule} - {detail}"

class DocumentProcessingError(OrchestratorException):
    """Raised when document extraction fails permanently"""
    http_status = 500
    error_code = "ORCHESTRATOR_004"
    message_pattern = "Document processing failed for {document_id}: {error}"

class FintracVerificationError(OrchestratorException):
    """Raised when identity verification cannot be recorded"""
    http_status = 409
    error_code = "FINTRAC_001"
    message_pattern = "FINTRAC verification already exists for application {application_id}"

class FintracReportThresholdError(OrchestratorException):
    """Raised when transaction amount is below reporting threshold"""
    http_status = 400
    error_code = "FINTRAC_002"
    message_pattern = "Transaction amount {amount} is below FINTRAC threshold of $10,000"

class FintracDuplicateReportError(OrchestratorException):
    """Raised when report already filed"""
    http_status = 409
    error_code = "FINTRAC_003"
    message_pattern = "FINTRAC report already filed for application {application_id}"

class FintracClientNotFoundError(OrchestratorException):
    """Raised when client risk assessment has no data"""
    http_status = 404
    error_code = "FINTRAC_004"
    message_pattern = "Client {client_id} has no application history"
```

### 6.2 Error Response Format

All errors return consistent JSON:
```json
{
  "detail": "Application 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "ORCHESTRATOR_001",
  "module": "orchestrator",
  "timestamp": "2024-01-15T14:30:00Z",
  "correlation_id": "abc-123-def-456",
  "request_id": "req-789-xyz"
}
```

### 6.3 Monitoring & Alerting

**Prometheus Metrics:**
- `orchestrator_applications_total{status}`: Counter
- `orchestrator_processing_duration_seconds`: Histogram (buckets: 30s, 1m, 5m, 10m)
- `orchestrator_celery_task_failures_total{task_name}`: Counter
- `orchestrator_fintrac_reports_filed_total`: Counter
- `orchestrator_decision_ratio_violations_total{ratio_type}`: Counter (for OSFI compliance monitoring)

**Alerts:**
- High failure rate (>5%) on `extract_documents` → PagerDuty
- FINTRAC report filing delay > 14 days → Critical alert
- GDS/TDS calculation errors → Log to security audit stream
- Dead letter queue depth > 10 → Warning

---

**Next Steps for Implementation:**
1. Create module directory: `modules/orchestrator_service/`
2. Implement models.py with encryption helpers
3. Set up Celery app with task definitions and retry policies
4. Implement routes.py with input validation (Pydantic)
5. Write Alembic migration using spec above
6. Add unit tests for state machine transitions
7. Add integration tests for full pipeline flow
8. Configure Prometheus metrics and alerts
9. Set up mTLS certificates via Vault
10. Document API in OpenAPI 3.1 with security schemes