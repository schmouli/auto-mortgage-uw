# FINTRAC Compliance
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# FINTRAC Compliance Module Design

**Module Path:** `modules/fintrac/`  
**Design Document:** `docs/design/fintrac-compliance.md`  
**Last Updated:** 2024-01-15

---

## 1. Endpoints

### Authentication & Authorization
All endpoints require JWT authentication. Role-based access control:
- `compliance_officer`: Full access to verification and reporting
- `underwriter`: Read access to verification and risk assessment
- `admin`: Full access plus configuration management

---

### `POST /api/v1/fintrac/applications/{application_id}/verify-identity`

Submit identity verification record for a client associated with a mortgage application.

**Request Body Schema (`schemas.IdentityVerificationCreate`)**
```python
{
  "client_id": UUID,                          # Required
  "verification_method": Enum["in_person", "credit_file", "dual_process"],  # Required
  "id_type": str,                             # Required: "drivers_license", "passport", etc.
  "id_number": str,                           # Required: Plaintext ID number (encrypted at rest)
  "id_expiry_date": date,                     # Required
  "id_issuing_province": str,                 # Required: 2-letter province code
  "is_pep": bool,                             # Required
  "is_hio": bool,                             # Required
}
```

**Response Schema (`schemas.IdentityVerificationResponse`)**
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
  "risk_level": Enum["low", "medium", "high"],
  "record_created_at": datetime,
}
```

**Error Responses**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| `400` | `FINTRAC_003` | Invalid `verification_method` or `id_type` |
| `404` | `FINTRAC_001` | Application or client not found |
| `409` | `FINTRAC_004` | Verification already exists for this client/application (idempotent creation allowed with 200 if duplicate exact data) |
| `422` | `FINTRAC_003` | `id_expiry_date` in past or `id_issuing_province` invalid |

**Auth:** `compliance_officer`, `underwriter`

---

### `GET /api/v1/fintrac/applications/{application_id}/verification`

Retrieve all identity verification records for an application.

**Response Schema (`schemas.IdentityVerificationListResponse`)**
```python
{
  "application_id": UUID,
  "verifications": List[schemas.IdentityVerificationResponse],
  "count": int,
}
```

**Error Responses**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| `404` | `FINTRAC_001` | Application not found |

**Auth:** `compliance_officer`, `underwriter`

---

### `POST /api/v1/fintrac/applications/{application_id}/report-transaction`

File a FINTRAC transaction report (LCTR, STR, or terrorist property).

**Request Body Schema (`schemas.TransactionReportCreate`)**
```python
{
  "report_type": Enum["large_cash_transaction", "suspicious_transaction", "terrorist_property"],  # Required
  "amount": Decimal,                          # Required: Transaction amount
  "currency": str = "CAD",                    # Required: ISO 4217 code
  "transaction_date": datetime,               # Required
  "suspicion_details": Optional[str],         # Required if report_type="suspicious_transaction"
}
```

**Response Schema (`schemas.TransactionReportResponse`)**
```python
{
  "report_id": UUID,
  "application_id": UUID,
  "report_type": str,
  "amount": Decimal,
  "currency": str,
  "transaction_date": datetime,
  "report_date": datetime,
  "submitted_to_fintrac_at": Optional[datetime],
  "fintrac_reference_number": Optional[str],
  "created_by": UUID,
  "record_created_at": datetime,
}
```

**Error Responses**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| `400` | `FINTRAC_003` | `report_type` invalid or `amount` negative |
| `404` | `FINTRAC_001` | Application not found |
| `409` | `FINTRAC_004` | Report already filed for identical transaction (deduplication check) |
| `422` | `FINTRAC_006` | `amount` ≤ $10,000 CAD for `large_cash_transaction` (threshold check) |

**Auth:** `compliance_officer` only

---

### `GET /api/v1/fintrac/applications/{application_id}/reports`

List all FINTRAC reports for an application.

**Response Schema (`schemas.TransactionReportListResponse`)**
```python
{
  "application_id": UUID,
  "reports": List[schemas.TransactionReportResponse],
  "count": int,
}
```

**Error Responses**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| `404` | `FINTRAC_001` | Application not found |

**Auth:** `compliance_officer`, `underwriter`

---

### `GET /api/v1/fintrac/risk-assessment/{client_id}`

Get consolidated risk assessment for a client across all applications.

**Response Schema (`schemas.ClientRiskAssessmentResponse`)**
```python
{
  "client_id": UUID,
  "overall_risk_level": Enum["low", "medium", "high"],
  "pep_flag": bool,
  "hio_flag": bool,
  "verification_count": int,
  "high_risk_application_count": int,
  "fintrac_reports_count": int,
  "last_verified_at": Optional[datetime],
}
```

**Error Responses**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| `404` | `FINTRAC_007` | Client not found or no FINTRAC data |

**Auth:** `compliance_officer`, `underwriter`

---

## 2. Models & Database

### `fintrac_verifications` Table

| Column | Type | Constraints | Index | Notes |
|--------|------|-------------|-------|-------|
| `id` | `UUID` | PK, default gen_random_uuid() | Primary | Immutable |
| `application_id` | `UUID` | NOT NULL, FK → applications.id | IDX (composite) | ON DELETE RESTRICT |
| `client_id` | `UUID` | NOT NULL, FK → clients.id | IDX (composite) | ON DELETE RESTRICT |
| `verification_method` | `VARCHAR(20)` | NOT NULL, CHECK IN (...) | - | Enum: `in_person`, `credit_file`, `dual_process` |
| `id_type` | `VARCHAR(50)` | NOT NULL | - | e.g., `drivers_license`, `passport` |
| `id_number_encrypted` | `BYTEA` | NOT NULL | - | AES-256-GCM encrypted via `encrypt_pii()` |
| `id_expiry_date` | `DATE` | NOT NULL | - | Must be ≥ current date |
| `id_issuing_province` | `VARCHAR(2)` | NOT NULL, CHECK length=2 | - | Province code (AB, BC, etc.) |
| `verified_by` | `UUID` | NOT NULL, FK → users.id | IDX | Compliance officer user ID |
| `verified_at` | `TIMESTAMP` | NOT NULL, default now() | - | When verification completed |
| `is_pep` | `BOOLEAN` | NOT NULL, default false | - | Politically Exposed Person flag |
| `is_hio` | `BOOLEAN` | NOT NULL, default false | - | Head of International Organization flag |
| `risk_level` | `VARCHAR(10)` | NOT NULL, CHECK IN (...) | - | Enum: `low`, `medium`, `high` |
| `record_created_at` | `TIMESTAMP` | NOT NULL, default now() | - | **Audit field** |
| `record_updated_at` | `TIMESTAMP` | NOT NULL, default now() | - | **Audit field** |
| `deleted_at` | `TIMESTAMP` | NULL | IDX | Soft-delete marker |

**Indexes:**
```sql
CREATE INDEX idx_fintrac_verifications_app_client ON fintrac_verifications(application_id, client_id);
CREATE INDEX idx_fintrac_verifications_verified_by ON fintrac_verifications(verified_by);
CREATE INDEX idx_fintrac_verifications_deleted_at ON fintrac_verifications(deleted_at) WHERE deleted_at IS NOT NULL;
```

**Relationships:**
- `application_id` → `applications.id` (RESTRICT)
- `client_id` → `clients.id` (RESTRICT)
- `verified_by` → `users.id` (RESTRICT)

**Compliance Notes:**
- **PIPEDA**: `id_number_encrypted` must never be logged or returned in APIs. Use SHA-256 hash for deduplication checks if needed.
- **FINTRAC**: Records immutable after creation. Updates must create new version and soft-delete old.

---

### `fintrac_reports` Table

| Column | Type | Constraints | Index | Notes |
|--------|------|-------------|-------|-------|
| `id` | `UUID` | PK, default gen_random_uuid() | Primary | Immutable |
| `application_id` | `UUID` | NOT NULL, FK → applications.id | IDX | ON DELETE RESTRICT |
| `report_type` | `VARCHAR(30)` | NOT NULL, CHECK IN (...) | IDX | Enum: `large_cash_transaction`, `suspicious_transaction`, `terrorist_property` |
| `amount` | `DECIMAL(15,2)` | NOT NULL, CHECK > 0 | - | **Decimal for financial values** |
| `currency` | `VARCHAR(3)` | NOT NULL, default 'CAD' | - | ISO 4217 code |
| `transaction_date` | `TIMESTAMP` | NOT NULL | - | When transaction occurred |
| `report_date` | `TIMESTAMP` | NOT NULL, default now() | - | When report created in system |
| `submitted_to_fintrac_at` | `TIMESTAMP` | NULL | IDX | When successfully submitted to FINTRAC |
| `fintrac_reference_number` | `VARCHAR(100)` | NULL | - | FINTRAC confirmation number |
| `created_by` | `UUID` | NOT NULL, FK → users.id | IDX | User who filed report |
| `record_created_at` | `TIMESTAMP` | NOT NULL, default now() | - | **Audit field** |
| `record_updated_at` | `TIMESTAMP` | NOT NULL, default now() | - | **Audit field** |
| `deleted_at` | `TIMESTAMP` | NULL | IDX | Soft-delete marker |

**Indexes:**
```sql
CREATE INDEX idx_fintrac_reports_application_id ON fintrac_reports(application_id);
CREATE INDEX idx_fintrac_reports_report_type ON fintrac_reports(report_type);
CREATE INDEX idx_fintrac_reports_submitted_at ON fintrac_reports(submitted_to_fintrac_at);
CREATE INDEX idx_fintrac_reports_deleted_at ON fintrac_reports(deleted_at) WHERE deleted_at IS NOT NULL;
```

**Relationships:**
- `application_id` → `applications.id` (RESTRICT)
- `created_by` → `users.id` (RESTRICT)

**Compliance Notes:**
- **FINTRAC**: `amount` must be in CAD for threshold checks. Convert if `currency != 'CAD'` using daily FX rates (via `common.fx_rates` service).
- **FINTRAC**: `submitted_to_fintrac_at` and `fintrac_reference_number` must be populated only after successful API submission.
- **Record Retention**: Soft-delete only; purging after 5 years is out-of-scope (archival process).

---

## 3. Business Logic

### 3.1 Identity Verification Workflow

**Trigger:** Client submits mortgage application → Underwriter initiates verification.

**Steps:**
1. **Validation:**
   - `verification_method` must be allowed for client's province (e.g., `dual_process` required for QC).
   - `id_expiry_date` must be ≥ today + 30 days (buffer).
   - `id_number` must be non-empty and pass format validation (regex per `id_type`).
   - `is_pep`/`is_hio` flags must be confirmed via external watchlist check (see §3.4).

2. **Risk Level Calculation (Algorithm):**
   ```python
   risk_score = 0
   
   # PEP/HIO flags (FINTRAC requirement)
   if is_pep or is_hio:
       risk_score += 3
   
   # Verification method weighting
   if verification_method == "credit_file":
       risk_score += 1
   elif verification_method == "in_person":
       risk_score += 0
   elif verification_method == "dual_process":
       risk_score += 0
   
   # Province risk (example: BC/ON lower, territories higher)
   if id_issuing_province in ["NT", "NU", "YT"]:
       risk_score += 1
   
   # Score to level mapping
   if risk_score >= 4:
       risk_level = "high"
   elif risk_score >= 2:
       risk_level = "medium"
   else:
       risk_level = "low"
   ```
   **WARNING:** PEP/HIO list integration and risk scoring weights are not finalized. The algorithm must be configurable via `common/config.py` and audited before production.

3. **Enhanced Due Diligence (EDD) Trigger:**
   - If `risk_level == "high"` OR `is_pep == True` OR `is_hio == True`:
     - Block application status from moving to `approved` until EDD checklist completed.
     - Log EDD requirement with `correlation_id` for audit.
     - Create task in `compliance_tasks` table (out-of-scope).

4. **Storage:**
   - Encrypt `id_number` using `common.security.encrypt_pii()` before persistence.
   - Insert record with `verified_by` = current user, `verified_at` = now().
   - **Immutability:** Once created, only soft-delete is allowed. Corrections require new record.

### 3.2 Transaction Monitoring & Reporting

**Large Cash Transaction (LCTR) Detection:**
- **Threshold:** `amount > CAD $10,000` (configurable via `FINTRAC_LCTR_THRESHOLD` in `common/config.py`).
- **Currency Conversion:** If `currency != 'CAD'`, convert using `common.fx_rates.get_cad_equivalent()` with transaction_date FX rate.
- **Structuring Detection:**
  - Query `fintrac_reports` for same `application_id` and `client_id` where:
    - `transaction_date` within 24 hours of current transaction
    - `amount` < $10,000 individually
    - `report_type = 'large_cash_transaction'`
  - If sum of such transactions ≥ $10,000 → flag as structuring and create single LCTR with aggregated amount.

**Report Submission to FINTRAC:**
- **Async Worker:** Use Celery task (or equivalent) to submit reports to FINTRAC API to avoid blocking API response.
- **Retry Logic:** Exponential backoff (3 attempts) with circuit breaker pattern.
- **Success:** Populate `submitted_to_fintrac_at` and `fintrac_reference_number`.
- **Failure:** Alert via `common.alerts.send_compliance_alert()` and retry manually.

**Report Types:**
- `large_cash_transaction`: Auto-generated by threshold breach.
- `suspicious_transaction`: Manually filed via API when underwriter flags unusual activity.
- `terrorist_property`: Manually filed, requires admin approval.

### 3.3 Record Retention & Soft Delete

- **Soft Delete:** All DELETE operations set `deleted_at = now()`. Records remain queryable with `WHERE deleted_at IS NULL` filter.
- **Retention Period:** 5 years from `record_created_at`. Purging is out-of-scope; design separate archival service.
- **Audit Trail:** All actions (create, soft-delete, submission) logged to `audit_log` table with `correlation_id`, `user_id`, `action`, `table_name`, `record_id`.

### 3.4 PEP/HIO Watchlist Integration

**WARNING:** Integration details not specified. Design placeholder:

- External service: `services.PepHioWatchlistService` (interface defined, implementation TBD).
- Update mechanism: Daily batch job fetches latest sanctions list from FINTRAC/OSFI API and updates `pep_hio_watchlist` table.
- Verification check: During identity verification, query `pep_hio_watchlist` by `id_number_hash` (SHA-256) to confirm PEP/HIO status.
- Caching: Redis cache for watchlist entries with 1-hour TTL.

---

## 4. Migrations

**Alembic Migration:** `migrations/versions/YYYYMMDDHHMMSS_create_fintrac_tables.py`

```python
def upgrade():
    # fintrac_verifications table
    op.create_table(
        'fintrac_verifications',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('verification_method', sa.String(length=20), nullable=False),
        sa.Column('id_type', sa.String(length=50), nullable=False),
        sa.Column('id_number_encrypted', sa.LargeBinary(), nullable=False),
        sa.Column('id_expiry_date', sa.Date(), nullable=False),
        sa.Column('id_issuing_province', sa.String(length=2), nullable=False),
        sa.Column('verified_by', sa.UUID(), nullable=False),
        sa.Column('verified_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_pep', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_hio', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('risk_level', sa.String(length=10), nullable=False),
        sa.Column('record_created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('record_updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("verification_method IN ('in_person', 'credit_file', 'dual_process')", name='check_verification_method'),
        sa.CheckConstraint("risk_level IN ('low', 'medium', 'high')", name='check_risk_level'),
        sa.CheckConstraint("length(id_issuing_province) = 2", name='check_province_length'),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes
    op.create_index('idx_fintrac_verifications_app_client', 'fintrac_verifications', ['application_id', 'client_id'])
    op.create_index('idx_fintrac_verifications_verified_by', 'fintrac_verifications', ['verified_by'])
    op.create_index('idx_fintrac_verifications_deleted_at', 'fintrac_verifications', ['deleted_at'], 
                    postgresql_where=sa.text('deleted_at IS NOT NULL'))
    
    # fintrac_reports table
    op.create_table(
        'fintrac_reports',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('report_type', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.DECIMAL(precision=15, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), server_default='CAD', nullable=False),
        sa.Column('transaction_date', sa.DateTime(), nullable=False),
        sa.Column('report_date', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('submitted_to_fintrac_at', sa.DateTime(), nullable=True),
        sa.Column('fintrac_reference_number', sa.String(length=100), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('record_created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('record_updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("report_type IN ('large_cash_transaction', 'suspicious_transaction', 'terrorist_property')", name='check_report_type'),
        sa.CheckConstraint('amount > 0', name='check_amount_positive'),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes
    op.create_index('idx_fintrac_reports_application_id', 'fintrac_reports', ['application_id'])
    op.create_index('idx_fintrac_reports_report_type', 'fintrac_reports', ['report_type'])
    op.create_index('idx_fintrac_reports_submitted_at', 'fintrac_reports', ['submitted_to_fintrac_at'])
    op.create_index('idx_fintrac_reports_deleted_at', 'fintrac_reports', ['deleted_at'], 
                    postgresql_where=sa.text('deleted_at IS NOT NULL'))
```

**Data Migration:** None required (new module).

---

## 5. Security & Compliance

### PIPEDA (Personal Information Protection)
- **Encryption:** `id_number_encrypted` encrypted via `common.security.encrypt_pii()` using AES-256-GCM. Encryption key rotated quarterly.
- **Data Minimization:** Only collect ID fields required for FINTRAC verification. No SIN or DOB stored in this module.
- **Logging:** Never log plaintext `id_number`. Log only `verification_id` and `client_id` for traceability.
- **Access Control:** Role-based access; ID numbers only decryptable by `compliance_officer` role.

### FINTRAC Requirements
- **Immutability:** Verification records cannot be updated. Corrections require new record creation and soft-delete of old. Enforced at service layer (`services.FintracVerificationService.create()` only; no `update()` method).
- **Retention:** Soft-delete only. Physical purging after 5 years handled by separate archival job.
- **Threshold Monitoring:** Large cash transaction detection runs synchronously on deposit webhook (from `payments` module) and asynchronously via daily batch for structuring checks.
- **Submission:** FINTRAC API integration must use mTLS authentication. Reference numbers stored only after successful submission.
- **Audit Trail:** All actions logged to `audit_log` table with `action_type` IN ('fintrac_verification_created', 'fintrac_report_filed', 'fintrac_record_soft_deleted').

### OSFI B-20 Interaction
- FINTRAC module does not calculate GDS/TDS, but **must not block** OSFI-compliant underwriting workflows. If EDD is pending, underwriting status should be `pending_compliance` rather than `rejected`.

### Authentication & Authorization
- **JWT Claims Required:** `sub` (user_id), `roles` (array), `correlation_id`.
- **Middleware:** `common.security.require_roles()` decorator on all endpoints.
- **mTLS:** FINTRAC API client must use mutual TLS (certs stored in HashiCorp Vault, mounted via `common.config`).

---

## 6. Error Codes & HTTP Responses

**Base Exception:** `FintracException(AppException)` in `modules/fintrac/exceptions.py`

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `FintracVerificationNotFoundError` | `404` | `FINTRAC_001` | "Verification record not found for application {application_id}" | GET verification when no records exist |
| `FintracReportNotFoundError` | `404` | `FINTRAC_002` | "Report not found for application {application_id}" | GET single report by ID (if implemented) |
| `FintracValidationError` | `422` | `FINTRAC_003` | "{field}: {reason}" | Invalid `verification_method` or expired ID |
| `FintracBusinessRuleError` | `409` | `FINTRAC_004` | "Business rule violated: {detail}" | Duplicate verification with mismatched data |
| `FintracEnhancedDueDiligenceRequiredError` | `403` | `FINTRAC_005` | "Enhanced due diligence required for PEP/HIO/high-risk client" | Underwriter attempts approval before EDD complete |
| `FintracTransactionThresholdError` | `422` | `FINTRAC_006` | "Transaction amount below reporting threshold" | Manual report filing under $10,000 |
| `FintracClientRiskNotFoundError` | `404` | `FINTRAC_007` | "Risk assessment not found for client {client_id}" | No verification/report data for client |
| `FintracSubmissionFailedError` | `502` | `FINTRAC_008` | "FINTRAC submission failed: {detail}" | Async worker fails after retries |

**Error Response Format (FastAPI Exception Handler):**
```json
{
  "detail": "Verification record not found for application 123e4567-e89b-12d3-a456-426614174000",
  "error_code": "FINTRAC_001",
  "correlation_id": "req-abc123",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

---

## 7. Missing Details & Warnings

**⚠️ PEP/HIO List Integration:** No external API or data source specified. Design includes placeholder service interface, but implementation and update frequency must be defined before development.

**⚠️ Risk Scoring Algorithm:** Weights and provincial risk tiers are illustrative only. Must be validated with compliance team and made configurable.

**⚠️ FINTRAC Submission API:** Endpoint URL, authentication method (mTLS certs), request/response schemas, and retry policies are not documented. Requires separate integration design.

**⚠️ Transaction Monitoring Threshold Tuning:** Structuring detection window (24h) and threshold ($10,000) must be configurable and tested with historical data.

**⚠️ Audit Trail Immutability:** While soft-delete is implemented, true immutability may require blockchain or WORM storage for FINTRAC audits. Current design relies on application-level enforcement.

**⚠️ FX Rate Source:** For non-CAD transactions, FX rate provider and caching strategy not specified. Must integrate with `common.fx_rates` service.

---

## 8. Dependencies

- **Core Modules:** `applications`, `clients`, `users` (must exist for FKs)
- **Common Services:** `common.security.encrypt_pii`, `common.database.get_async_session`, `common.config.Settings`
- **External:** FINTRAC Reporting API (REST/SOAP), PEP/HIO watchlist feed, FX rate provider

---

## 9. Testing Strategy

- **Unit Tests:** Mock encryption, validation logic, risk scoring algorithm edge cases.
- **Integration Tests:** Full workflow with `applications` module, soft-delete behavior, transaction threshold detection.
- **Compliance Tests:** Verify 5-year retention query, immutability attempts, audit log entries.
- **Load Tests:** Async FINTRAC submission worker under high report volume.

**Test Markers:** `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.compliance`

---

## 10. Deployment Notes

- **Secrets:** FINTRAC API mTLS certs, encryption keys stored in Vault. Mapped via `common.config.VaultSettings`.
- **Workers:** Deploy Celery worker pool for report submission. Monitor with OpenTelemetry.
- **Monitoring:** Prometheus metrics for `fintrac_reports_submitted_total`, `fintrac_verification_risk_level_distribution`.
- **Alerts:** Alert on `FINTRAC_005` (EDD required) and submission failures (`FINTRAC_008`).