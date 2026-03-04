# Design: FINTRAC Compliance
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# FINTRAC Compliance Module Design Plan

**File:** `docs/design/fintrac-compliance.md`  
**Module:** `fintrac/`  
**Feature Slug:** `fintrac-compliance`  
**Last Updated:** 2024-01-15

---

## 1. Endpoints

### 1.1 POST /api/v1/fintrac/applications/{id}/verify-identity
Submit identity verification for a client in an application.

**Path Parameters:**
- `id`: UUID — Application ID

**Request Body Schema (`IdentityVerificationRequest`):**
```python
{
    "client_id": UUID,                          # Required
    "verification_method": Enum["in_person", "credit_file", "dual_process"],  # Required
    "id_type": str,                             # Required: "driver_license", "passport", "provincial_id"
    "id_number": str,                           # Required: Plaintext, encrypted at rest
    "id_expiry_date": date,                     # Required
    "id_issuing_province": str,                 # Required: 2-letter province code (e.g., "ON", "BC")
    "is_pep": bool,                             # Optional: default false
    "is_hio": bool,                             # Optional: default false
    "risk_level": Enum["low", "medium", "high"] # Optional: default "low"
}
```

**Response Schema (`IdentityVerificationResponse`):**
```python
{
    "verification_id": UUID,
    "application_id": UUID,
    "client_id": UUID,
    "verification_method": str,
    "id_type": str,
    "id_expiry_date": date,
    "id_issuing_province": str,
    "verified_by": UUID,
    "verified_at": datetime,
    "is_pep": bool,
    "is_hio": bool,
    "risk_level": str,
    "requires_enhanced_due_diligence": bool,  # Computed: true if risk_level=high or is_pep=true or is_hio=true
    "created_at": datetime
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 400 | FINTRAC_002 | "Invalid verification method: {value}" |
| 404 | APPLICATION_001 | "Application not found" |
| 404 | CLIENT_001 | "Client not found" |
| 409 | FINTRAC_003 | "Identity verification already exists for client {client_id}" |
| 422 | FINTRAC_002 | "id_expiry_date cannot be in the past" |

**Authentication:** Authenticated (Underwriter, Admin roles only)

---

### 1.2 GET /api/v1/fintrac/applications/{id}/verification
Retrieve identity verification status for all clients in an application.

**Path Parameters:**
- `id`: UUID — Application ID

**Query Parameters:**
- `include_deleted`: bool = false — Include soft-deleted records (admin only)

**Response Schema (`VerificationStatusResponse`):**
```python
{
    "application_id": UUID,
    "verifications": List[{
        "verification_id": UUID,
        "client_id": UUID,
        "verification_method": str,
        "id_type": str,
        "id_expiry_date": date,
        "verified_at": datetime,
        "is_pep": bool,
        "is_hio": bool,
        "risk_level": str,
        "requires_enhanced_due_diligence": bool,
        "status": Enum["verified", "expired", "flagged"]
    }],
    "all_clients_verified": bool,
    "enhanced_due_diligence_required": bool  # True if any client requires EDD
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 404 | APPLICATION_001 | "Application not found" |
| 403 | AUTH_003 | "Admin role required to include deleted records" |

**Authentication:** Authenticated (any role)

---

### 1.3 POST /api/v1/fintrac/applications/{id}/report-transaction
File a FINTRAC report for large cash, suspicious, or terrorist property transaction.

**Path Parameters:**
- `id`: UUID — Application ID

**Request Body Schema (`TransactionReportRequest`):**
```python
{
    "report_type": Enum["large_cash_transaction", "suspicious_transaction", "terrorist_property"],  # Required
    "amount": Decimal,                          # Required: > 0
    "currency": str = "CAD",                    # ISO 4217 code
    "transaction_date": date,                   # Required
    "client_id": UUID,                          # Required
    "structuring_indicators": List[str],        # Optional: e.g., ["multiple_deposits", "just_below_threshold"]
    "narrative": str                            # Optional: Required for suspicious_transaction type
}
```

**Response Schema (`TransactionReportResponse`):**
```python
{
    "report_id": UUID,
    "application_id": UUID,
    "report_type": str,
    "amount": Decimal,
    "currency": str,
    "transaction_date": date,
    "submitted_to_fintrac_at": datetime | null,
    "fintrac_reference_number": str | null,
    "status": Enum["draft", "submitted", "acknowledged", "rejected"],
    "created_by": UUID,
    "created_at": datetime,
    "requires_immediate_filing": bool  # True if amount > 10,000 CAD or structuring detected
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 400 | FINTRAC_002 | "Amount must be positive Decimal value" |
| 400 | FINTRAC_003 | "Narrative required for suspicious_transaction type" |
| 404 | APPLICATION_001 | "Application not found" |
| 409 | FINTRAC_003 | "Duplicate report for transaction {transaction_date}" |
| 422 | FINTRAC_002 | "Currency must be 3-letter ISO code" |

**Authentication:** Authenticated (Underwriter, Admin roles only)

---

### 1.4 GET /api/v1/fintrac/applications/{id}/reports
List all FINTRAC reports for an application with pagination.

**Path Parameters:**
- `id`: UUID — Application ID

**Query Parameters:**
- `report_type`: Optional filter
- `page`: int = 1
- `page_size`: int = 50 (max 200)
- `include_deleted`: bool = false (admin only)

**Response Schema (`TransactionReportListResponse`):**
```python
{
    "application_id": UUID,
    "reports": List[TransactionReportResponse],
    "pagination": {
        "page": int,
        "page_size": int,
        "total_count": int,
        "total_pages": int
    },
    "summary": {
        "total_reports": int,
        "large_cash_transactions": int,
        "suspicious_transactions": int,
        "pending_submission": int
    }
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 404 | APPLICATION_001 | "Application not found" |
| 403 | AUTH_003 | "Admin role required to include deleted records" |

**Authentication:** Authenticated (any role)

---

### 1.5 GET /api/v1/fintrac/risk-assessment/{client_id}
Get consolidated risk assessment for a client across all applications.

**Path Parameters:**
- `client_id`: UUID

**Response Schema (`ClientRiskAssessmentResponse`):**
```python
{
    "client_id": UUID,
    "overall_risk_level": Enum["low", "medium", "high"],
    "risk_factors": List[{
        "factor": str,
        "weight": float,
        "score": float
    }],
    "pep_hio_status": {
        "is_pep": bool,
        "is_hio": bool,
        "last_verified": datetime,
        "source": str  # "manual", "automated_screening"
    },
    "transaction_patterns": {
        "total_cash_transactions_24h": Decimal,
        "structuring_flags": int,
        "last_flagged": datetime | null
    },
    "applications": List[{
        "application_id": UUID,
        "verification_status": str,
        "risk_level": str,
        "mortgage_amount": Decimal
    }],
    "recommendation": Enum["standard_processing", "enhanced_due_diligence", "decline"]
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 404 | CLIENT_001 | "Client not found" |
| 404 | FINTRAC_005 | "No FINTRAC records found for client" |

**Authentication:** Authenticated (Underwriter, Admin roles only)

---

## 2. Models & Database

### 2.1 fintrac_verifications Table

**Table Name:** `fintrac_verifications`

| Column | Type | Constraints | Index | Notes |
|--------|------|-------------|-------|-------|
| `id` | UUID | PRIMARY KEY | Yes (pk) | Generated uuid4 |
| `application_id` | UUID | NOT NULL, FK → applications.id | Yes (composite) | CASCADE DELETE |
| `client_id` | UUID | NOT NULL, FK → clients.id | Yes (composite) | CASCADE DELETE |
| `verification_method` | VARCHAR(20) | NOT NULL, CHECK IN ('in_person','credit_file','dual_process') | No | - |
| `id_type` | VARCHAR(50) | NOT NULL | No | Document type |
| `id_number_encrypted` | VARCHAR(255) | NOT NULL | No | **AES-256 encrypted** (PIPEDA) |
| `id_expiry_date` | DATE | NOT NULL | No | - |
| `id_issuing_province` | VARCHAR(2) | NOT NULL, CHECK IN (province codes) | No | Two-letter code |
| `verified_by` | UUID | NOT NULL, FK → users.id | Yes | Who performed verification |
| `verified_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Yes | When verified |
| `is_pep` | BOOLEAN | NOT NULL, DEFAULT false | Yes | Politically Exposed Person |
| `is_hio` | BOOLEAN | NOT NULL, DEFAULT false | Yes | Head of International Org |
| `risk_level` | VARCHAR(10) | NOT NULL, DEFAULT 'low', CHECK IN ('low','medium','high') | Yes | Risk assessment |
| `record_created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Yes | FINTRAC audit timestamp |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Yes | Standard audit field |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW(), ON UPDATE NOW() | No | Standard audit field |
| `deleted_at` | TIMESTAMP | NULL | Yes (partial) | Soft delete marker |

**Indexes:**
```sql
CREATE INDEX idx_verifications_application_client ON fintrac_verifications(application_id, client_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_verifications_verified_by ON fintrac_verifications(verified_by) WHERE deleted_at IS NULL;
CREATE INDEX idx_verifications_risk_level ON fintrac_verifications(risk_level) WHERE deleted_at IS NULL;
CREATE INDEX idx_verifications_pep_hio ON fintrac_verifications(is_pep, is_hio) WHERE deleted_at IS NULL;
```

**Relationships:**
- Many-to-one: `application` → applications.id
- Many-to-one: `client` → clients.id
- Many-to-one: `verifier` → users.id

---

### 2.2 fintrac_reports Table

**Table Name:** `fintrac_reports`

| Column | Type | Constraints | Index | Notes |
|--------|------|-------------|-------|-------|
| `id` | UUID | PRIMARY KEY | Yes (pk) | Generated uuid4 |
| `application_id` | UUID | NOT NULL, FK → applications.id | Yes (composite) | CASCADE DELETE |
| `report_type` | VARCHAR(30) | NOT NULL, CHECK IN ('large_cash_transaction','suspicious_transaction','terrorist_property') | Yes | Report category |
| `amount` | DECIMAL(15,2) | NOT NULL, CHECK > 0 | Yes | **Decimal for financial** |
| `currency` | VARCHAR(3) | NOT NULL, DEFAULT 'CAD' | No | ISO 4217 code |
| `transaction_date` | DATE | NOT NULL | Yes | When transaction occurred |
| `submitted_to_fintrac_at` | TIMESTAMP | NULL | Yes | When filed with FINTRAC |
| `fintrac_reference_number` | VARCHAR(100) | NULL | Yes | FINTRAC acknowledgment |
| `created_by` | UUID | NOT NULL, FK → users.id | Yes | Who created report |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Yes | Standard audit field |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW(), ON UPDATE NOW() | No | Standard audit field |
| `deleted_at` | TIMESTAMP | NULL | Yes (partial) | Soft delete marker |

**Indexes:**
```sql
CREATE INDEX idx_reports_application ON fintrac_reports(application_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_reports_type_date ON fintrac_reports(report_type, transaction_date) WHERE deleted_at IS NULL;
CREATE INDEX idx_reports_submitted ON fintrac_reports(submitted_to_fintrac_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_reports_amount_threshold ON fintrac_reports(amount) WHERE deleted_at IS NULL AND amount > 10000;
```

**Relationships:**
- Many-to-one: `application` → applications.id
- Many-to-one: `creator` → users.id

---

### 2.3 Encryption & PII Handling

**PIPEDA Compliance:**
- `id_number_encrypted`: Must use `common/security.py:encrypt_pii()` with AES-256-GCM before storage
- **Never** log plaintext `id_number` — log only hashed SHA256 for debugging
- **Never** return `id_number_encrypted` in API responses
- Encryption key rotation: Use separate key per client or per application

---

## 3. Business Logic

### 3.1 Identity Verification Workflow

**Service:** `FintracVerificationService`

1. **Validation Phase:**
   - Verify application exists and is in `underwriting` state
   - Verify client exists and is linked to application
   - Check for existing verification (prevent duplicates)
   - Validate `id_expiry_date` > today
   - Validate province code against `common/config.py:CANADIAN_PROVINCES`

2. **Encryption Phase:**
   - Encrypt `id_number` using `encrypt_pii()` before DB write
   - Hash ID number (SHA256) for duplicate detection logging

3. **Risk Assessment Phase:**
   - Check against PEP/HIO database (see §3.4)
   - Calculate base risk score (see §3.3)
   - Determine if Enhanced Due Diligence (EDD) required:
     - EDD = True if (`risk_level == 'high'` OR `is_pep == True` OR `is_hio == True`)

4. **Audit Logging:**
   - Log: `verification_created`, `application_id`, `client_id`, `risk_level`, `edd_required`
   - **Do not log** `id_number` or PII

---

### 3.2 Transaction Monitoring & Structuring Detection

**Service:** `FintracTransactionMonitoringService`

**Large Cash Transaction Rule:**
- IF `amount > CAD 10,000.00` THEN `requires_immediate_filing = True`
- Currency conversion: Use `common/services/currency_converter.py` if `currency != 'CAD'`

**Structuring Detection Algorithm:**
```python
# Query all cash transactions for client in last 24 hours
structuring_sum = await db.execute(
    SELECT SUM(amount) FROM fintrac_reports 
    WHERE client_id = :client_id 
    AND report_type = 'large_cash_transaction'
    AND amount < 10000
    AND transaction_date >= NOW() - INTERVAL '24 hours'
    AND deleted_at IS NULL
)

IF structuring_sum >= 10000:
    flag_transaction("structuring_detected")
    create_suspicious_transaction_report(
        narrative=f"Multiple cash transactions totaling {structuring_sum} CAD within 24h"
    )
```

**Auto-Flagging Indicators:**
- ≥ 3 transactions < $10,000 within 24h from same client
- Round-number amounts (e.g., $9,900, $9,800)
- Rapid succession deposits (< 1 hour apart)

---

### 3.3 Risk Scoring Algorithm (Provisional)

**Service:** `FintracRiskScoringService`

Weights and thresholds configurable in `common/config.py:FINTRAC_RISK_CONFIG`

| Risk Factor | Weight | Scoring Logic |
|-------------|--------|---------------|
| **PEP/HIO Status** | 40% | `is_pep` or `is_hio` = 100 points |
| **Geographic Risk** | 20% | Province risk tier (BC/ON=low, territories=high) |
| **Transaction Velocity** | 15% | # transactions in 30 days > 5 = +20 pts |
| **Structuring History** | 15% | Previous flags = +30 pts per flag |
| **ID Document Type** | 10% | Passport=0, Provincial ID=10, Foreign ID=50 |

**Overall Risk Level:**
- **Low:** 0-30 points
- **Medium:** 31-60 points
- **High:** 61-100 points

**Recommendation Engine:**
- `standard_processing`: risk_level = low, no structuring flags
- `enhanced_due_diligence`: risk_level = medium OR PEP/HIO
- `decline`: risk_level = high OR structuring confirmed

---

### 3.4 PEP/HIO Database Integration (Stub Design)

**External Service:** `PEPHIO ScreeningService`

**Integration Pattern:**
- Async HTTP call to external screening API (e.g., World-Check, Refinitiv)
- Fallback to cached list in `fintrac_pep_hio_cache` table
- Update cache nightly via Celery/Arq job

**Cache Table Schema:**
```python
# Proposed future table
pep_hio_cache:
  - id: UUID
  - name_encrypted: VARCHAR  # AES-256
  - dob_encrypted: DATE      # AES-256
  - source: str               # "government_list", "commercial_api"
  - last_updated: TIMESTAMP
```

**Trigger:** Run screening on `POST /verify-identity` if `is_pep`/`is_hio` not manually set

---

### 3.5 FINTRAC Submission API Integration

**External Service:** `FintracFilingService`

**State Machine for Reports:**
```
draft → submitted → acknowledged → rejected
   ↑        ↓            ↓            ↓
   └────────┴────────────┴────────────┘
        (can resubmit if rejected)
```

**Submission Logic:**
1. Validate report completeness (narrative for suspicious transactions)
2. Convert to FINTRAC XML/JSON format (spec v4.2)
3. Sign with mTLS certificate (from `common/security.py`)
4. POST to FINTRAC API endpoint (configurable in `common/config.py:FINTRAC_API_URL`)
5. Store `fintrac_reference_number` on success
6. Retry on failure with exponential backoff (max 3 attempts)

**Async Processing:** Use Celery/Arq task queue for submission to avoid blocking API response

---

## 4. Migrations

### 4.1 New Tables

**Migration ID:** `2024_01_15_001_create_fintrac_tables.py`

```python
# Alembic operations
op.create_table(
    'fintrac_verifications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('application_id', sa.UUID(), nullable=False),
    sa.Column('client_id', sa.UUID(), nullable=False),
    sa.Column('verification_method', sa.String(length=20), nullable=False),
    sa.Column('id_type', sa.String(length=50), nullable=False),
    sa.Column('id_number_encrypted', sa.String(length=255), nullable=False),
    sa.Column('id_expiry_date', sa.Date(), nullable=False),
    sa.Column('id_issuing_province', sa.String(length=2), nullable=False),
    sa.Column('verified_by', sa.UUID(), nullable=False),
    sa.Column('verified_at', sa.DateTime(), nullable=False),
    sa.Column('is_pep', sa.Boolean(), nullable=False),
    sa.Column('is_hio', sa.Boolean(), nullable=False),
    sa.Column('risk_level', sa.String(length=10), nullable=False),
    sa.Column('record_created_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['verified_by'], ['users.id']),
    sa.PrimaryKeyConstraint('id')
)

op.create_table(
    'fintrac_reports',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('application_id', sa.UUID(), nullable=False),
    sa.Column('report_type', sa.String(length=30), nullable=False),
    sa.Column('amount', sa.DECIMAL(precision=15, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('transaction_date', sa.Date(), nullable=False),
    sa.Column('submitted_to_fintrac_at', sa.DateTime(), nullable=True),
    sa.Column('fintrac_reference_number', sa.String(length=100), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    sa.PrimaryKeyConstraint('id')
)
```

### 4.2 Indexes

```sql
-- fintrac_verifications indexes
CREATE INDEX idx_verifications_app_client ON fintrac_verifications(application_id, client_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_verifications_risk ON fintrac_verifications(risk_level) WHERE deleted_at IS NULL;
CREATE INDEX idx_verifications_pep_hio ON fintrac_verifications(is_pep, is_hio) WHERE deleted_at IS NULL;

-- fintrac_reports indexes
CREATE INDEX idx_reports_app ON fintrac_reports(application_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_reports_type_date ON fintrac_reports(report_type, transaction_date) WHERE deleted_at IS NULL;
CREATE INDEX idx_reports_submitted ON fintrac_reports(submitted_to_fintrac_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_reports_amount_threshold ON fintrac_reports(amount) WHERE deleted_at IS NULL AND amount > 10000;
```

### 4.3 Data Migration

**None required** for initial implementation. Future migrations may include:
- Backfill `record_created_at` from `created_at` for existing records
- Populate `fintrac_pep_hio_cache` table from external source

---

## 5. Security & Compliance

### 5.1 PIPEDA Data Handling

**Encryption Requirements:**
- `id_number_encrypted`: AES-256-GCM encryption in `services.py` before DB write
- Encryption key derived from `common/security.py:get_encryption_key(client_id, purpose="fintrac_id")`
- Key rotation: Annual rotation required; re-encrypt on first access after rotation

**Data Minimization:**
- Only collect ID number, type, expiry, and province — no full address or photo
- ID number **never** returned in API responses; only confirmation hash last 4 digits
- Auto-purge `id_number_encrypted` after 5-year retention period (mark for archival)

**Logging Restrictions:**
- **NEVER** log: `id_number`, client name, DOB, SIN, income
- **ALLOWED** log: `verification_id`, `application_id`, `risk_level`, `verification_method`
- Use `structlog` with `correlation_id` for audit trails

---

### 5.2 FINTRAC Record Retention

**MANDATORY:** 5-year retention from `record_created_at`

**Implementation:**
- Soft-delete only: Set `deleted_at` timestamp; never hard-delete
- Archive job: Quarterly, move records older than 5 years to `fintrac_archive` schema
- Archive table: Same schema + `archived_at` timestamp
- Access control: `fintrac_archive` readable only by `fintrac_auditor` role

**Audit Trail:**
- Every action (create, soft-delete, submit) logged to `fintrac_audit_log` table
- `fintrac_audit_log` columns: `id`, `table_name`, `record_id`, `action`, `performed_by`, `performed_at`, `ip_address`, `user_agent`

---

### 5.3 OSFI B-20 Interaction

**Not directly applicable** to FINTRAC module, but cross-module validation required:
- When `risk_level = 'high'` or `is_pep = True`, underwriting service must apply OSFI B-20 stress test at **qualifying_rate + 1%** (additional risk premium)
- GDS/TDS calculations must be **auditable** and include FINTRAC risk flags in breakdown

---

### 5.4 Authentication & Authorization

| Endpoint | Required Role | MFA Required | Notes |
|----------|---------------|--------------|-------|
| POST /verify-identity | underwriter, admin | Yes | Sensitive PII handling |
| GET /verification | underwriter, admin, viewer | No | Read-only |
| POST /report-transaction | underwriter, admin | Yes | Regulatory filing |
| GET /reports | underwriter, admin, viewer | No | Read-only |
| GET /risk-assessment | underwriter, admin | No | Sensitive data |

**API Key Access:** FINTRAC submission worker uses mTLS + service account token (no password)

---

## 6. Error Codes & HTTP Responses

### 6.1 Module Exception Classes

All exceptions inherit from `common.exceptions.AppException`

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `FintracVerificationNotFoundError` | 404 | FINTRAC_001 | "Identity verification not found for client {client_id}" | GET verification when none exists |
| `FintracValidationError` | 422 | FINTRAC_002 | "{field_name}: {validation_message}" | Invalid province code |
| `FintracBusinessRuleError` | 409 | FINTRAC_003 | "Business rule violated: {rule_detail}" | Duplicate verification |
| `FintracReportNotFoundError` | 404 | FINTRAC_004 | "FINTRAC report {report_id} not found" | GET non-existent report |
| `FintracRiskAssessmentNotFoundError` | 404 | FINTRAC_005 | "No risk assessment available for client {client_id}" | Client has no FINTRAC history |
| `FintracStructuringDetectedError` | 400 | FINTRAC_006 | "Structuring pattern detected: {detail}" | Multiple sub-threshold transactions |
| `FintracSubmissionFailedError` | 502 | FINTRAC_007 | "FINTRAC API submission failed: {error}" | External API timeout |

### 6.2 Global Exception Handling

**FastAPI Exception Handlers** in `routes.py`:

```python
@router.exception_handler(FintracBusinessRuleError)
async def handle_business_rule_error(request, exc):
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc), "error_code": "FINTRAC_003", "correlation_id": get_correlation_id()}
    )
```

**Structured Logging:** All exceptions logged with `error_code`, `correlation_id`, `user_id`, `application_id` for audit

---

## 7. Testing Strategy

### 7.1 Unit Tests (`tests/unit/test_fintrac.py`)
- Mock encryption service
- Test risk scoring algorithm with boundary values
- Test structuring detection with time-series data
- Validate PII is never logged

### 7.2 Integration Tests (`tests/integration/test_fintrac_integration.py`)
- Full workflow: verify identity → monitor transaction → file report
- Soft-delete behavior and 5-year retention query
- FINTRAC API mock server (WireMock) for submission testing
- Database constraints and index performance

### 7.3 Compliance Test Markers
```python
@pytest.mark.integration
@pytest.mark.fintrac_compliance
async def test_record_retention_5_years(db_session):
    # Verify records older than 5 years are archivable
    pass
```

---

## 8. Future Enhancements (Out of Scope)

1. **Automated PEP/HIO Screening:** Scheduled job to sync with government lists
2. **Transaction Monitoring Tuning:** Machine learning model for structuring detection
3. **FINTRAC API v5.0:** Upgrade path for new XML schema
4. **Real-time Alerting:** Slack/Email for high-risk verifications
5. **Client Risk Re-assessment:** Periodic re-verification every 12 months

---

**WARNING:** Missing details from requirements (PEP/HIO list integration, exact risk weights, FINTRAC API spec) are marked as **provisional** and require business stakeholder approval before implementation.