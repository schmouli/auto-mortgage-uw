# FINTRAC Compliance
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# docs/design/fintrac-compliance.md

## 1. Endpoints

### `POST /api/v1/fintrac/applications/{application_id}/verify-identity`
Submit identity verification for a client associated with a mortgage application.

**Authentication:** Authenticated (underwriter or admin role required)

**Request Body Schema:**
```json
{
  "client_id": "uuid (required)",
  "verification_method": "enum['in_person', 'credit_file', 'dual_process'] (required)",
  "id_type": "str[50] (required)",
  "id_number": "str (required, encrypted)",
  "id_expiry_date": "date (required)",
  "id_issuing_province": "str[2] (required, province code)",
  "is_pep": "bool (default: false)",
  "is_hio": "bool (default: false)",
  "risk_level": "enum['low', 'medium', 'high'] (optional, auto-calculated if omitted)"
}
```

**Response Schema (201 Created):**
```json
{
  "verification_id": "uuid",
  "application_id": "uuid",
  "client_id": "uuid",
  "verification_method": "str",
  "verified_at": "datetime",
  "risk_level": "str",
  "requires_enhanced_due_diligence": "bool",
  "status": "str"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or missing JWT token
- `403 Forbidden` - User lacks `underwriter` or `admin` role
- `404 Not Found` - Application or client does not exist (`FINTRAC_002`, `FINTRAC_003`)
- `422 Unprocessable Entity` - Validation failure (`FINTRAC_004`)
  - `id_expiry_date` in the past
  - Invalid `verification_method` or `id_issuing_province`
  - `id_number` format invalid

---

### `GET /api/v1/fintrac/applications/{application_id}/verification`
Retrieve verification status for all clients on an application.

**Authentication:** Authenticated (underwriter, admin, or auditor role)

**Path Parameter:** `application_id: uuid`

**Query Parameters:** `include_deleted: bool (default: false)` - Only available to admin role

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "verifications": [
    {
      "verification_id": "uuid",
      "client_id": "uuid",
      "verification_method": "str",
      "verified_at": "datetime",
      "verified_by": "uuid",
      "risk_level": "str",
      "is_pep": "bool",
      "is_hio": "bool",
      "requires_enhanced_due_diligence": "bool",
      "id_type": "str",
      "id_issuing_province": "str",
      "id_expiry_date": "date"
    }
  ],
  "overall_status": "str['pending', 'complete', 'requires_edr']"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or missing JWT token
- `403 Forbidden` - User lacks required role (`FINTRAC_006`)
- `404 Not Found` - Application does not exist (`FINTRAC_002`)

---

### `POST /api/v1/fintrac/applications/{application_id}/report-transaction`
File a FINTRAC transaction report (large cash, suspicious, or terrorist property).

**Authentication:** Authenticated (underwriter or admin role required)

**Request Body Schema:**
```json
{
  "report_type": "enum['large_cash_transaction', 'suspicious_transaction', 'terrorist_property'] (required)",
  "amount": "Decimal (precision: 15, scale: 2) (required)",
  "currency": "str[3] (default: 'CAD')",
  "transaction_date": "date (required)",
  "description": "str[500] (optional)",
  "client_id": "uuid (required)"
}
```

**Response Schema (201 Created):**
```json
{
  "report_id": "uuid",
  "application_id": "uuid",
  "client_id": "uuid",
  "report_type": "str",
  "amount": "Decimal",
  "currency": "str",
  "status": "enum['pending', 'submitted', 'failed']",
  "fintrac_reference_number": "str (nullable)",
  "submitted_to_fintrac_at": "datetime (nullable)"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or missing JWT token
- `403 Forbidden` - User lacks required role (`FINTRAC_006`)
- `404 Not Found` - Application or client does not exist (`FINTRAC_002`, `FINTRAC_003`)
- `422 Unprocessable Entity` - Validation failure (`FINTRAC_004`)
  - `amount` ≤ 0
  - `transaction_date` in the future
- `409 Conflict` - Business rule violation
  - Structuring pattern detected (`FINTRAC_005`)
  - Amount below CAD $10,000 threshold for large cash transactions
- `502 Bad Gateway` - FINTRAC API submission failed (`FINTRAC_008`)

---

### `GET /api/v1/fintrac/applications/{application_id}/reports`
List FINTRAC reports for an application with optional filtering.

**Authentication:** Authenticated (underwriter, admin, or auditor role)

**Path Parameter:** `application_id: uuid`

**Query Parameters:**
- `report_type: str (optional, filter)`
- `date_from: date (optional)`
- `date_to: date (optional)`
- `include_deleted: bool (default: false)` - Admin only

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "reports": [
    {
      "report_id": "uuid",
      "report_type": "str",
      "amount": "Decimal",
      "currency": "str",
      "transaction_date": "date",
      "report_date": "datetime",
      "submitted_to_fintrac_at": "datetime (nullable)",
      "fintrac_reference_number": "str (nullable)",
      "status": "str",
      "created_by": "uuid"
    }
  ],
  "total_count": "int"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or missing JWT token
- `403 Forbidden` - User lacks required role (`FINTRAC_006`)
- `404 Not Found` - Application does not exist (`FINTRAC_002`)

---

### `GET /api/v1/fintrac/risk-assessment/{client_id}`
Retrieve consolidated risk assessment for a client across all applications.

**Authentication:** Authenticated (underwriter, admin, or auditor role)

**Path Parameter:** `client_id: uuid`

**Response Schema (200 OK):**
```json
{
  "client_id": "uuid",
  "overall_risk_level": "enum['low', 'medium', 'high']",
  "risk_factors": ["str"],
  "verification_status": "enum['not_verified', 'verified', 'expired', 'requires_edr']",
  "pep_status": "bool",
  "hio_status": "bool",
  "last_verified_at": "datetime (nullable)",
  "applications_count": "int",
  "open_reports_count": "int"
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid or missing JWT token
- `403 Forbidden` - User lacks required role (`FINTRAC_006`)
- `404 Not Found` - Client has no verification records (`FINTRAC_001`)

---

## 2. Models & Database

### `fintrac_verifications` Table

**Table Name:** `fintrac_verifications`

**Columns:**
| Column Name | Type | Constraints | Index |
|-------------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY, default=gen_random_uuid() | - |
| `application_id` | UUID | FOREIGN KEY (applications.id), NOT NULL | ✓ |
| `client_id` | UUID | FOREIGN KEY (clients.id), NOT NULL | ✓ |
| `verification_method` | VARCHAR(20) | CHECK IN ('in_person', 'credit_file', 'dual_process'), NOT NULL | - |
| `id_type` | VARCHAR(50) | NOT NULL | - |
| `id_number_encrypted` | BYTEA | NOT NULL (AES-256) | - |
| `id_expiry_date` | DATE | NOT NULL | ✓ |
| `id_issuing_province` | VARCHAR(2) | NOT NULL | ✓ |
| `verified_by` | UUID | FOREIGN KEY (users.id), NOT NULL | ✓ |
| `verified_at` | TIMESTAMP | NOT NULL, default=now() | ✓ |
| `is_pep` | BOOLEAN | NOT NULL, default=false | ✓ |
| `is_hio` | BOOLEAN | NOT NULL, default=false | ✓ |
| `risk_level` | VARCHAR(10) | CHECK IN ('low', 'medium', 'high'), NOT NULL | ✓ |
| `record_created_at` | TIMESTAMP | NOT NULL, default=now() | ✓ |
| `created_at` | TIMESTAMP | NOT NULL, default=now() | - |
| `updated_at` | TIMESTAMP | NOT NULL, default=now(), onupdate=now() | - |
| `deleted_at` | TIMESTAMP | NULL (soft delete) | ✓ |

**Indexes:**
```sql
CREATE INDEX idx_finv_app_client ON fintrac_verifications(application_id, client_id);
CREATE INDEX idx_finv_client_verified_desc ON fintrac_verifications(client_id, verified_at DESC);
CREATE INDEX idx_finv_risk_flags ON fintrac_verifications(risk_level, is_pep, is_hio) 
  WHERE risk_level = 'high' OR is_pep = true OR is_hio = true;
CREATE INDEX idx_finv_province_expiry ON fintrac_verifications(id_issuing_province, id_expiry_date);
```

**Relationships:**
- Many-to-one with `applications` (ON DELETE RESTRICT)
- Many-to-one with `clients` (ON DELETE RESTRICT)
- Many-to-one with `users` (verified_by) (ON DELETE RESTRICT)

---

### `fintrac_reports` Table

**Table Name:** `fintrac_reports`

**Columns:**
| Column Name | Type | Constraints | Index |
|-------------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY, default=gen_random_uuid() | - |
| `application_id` | UUID | FOREIGN KEY (applications.id), NOT NULL | ✓ |
| `client_id` | UUID | FOREIGN KEY (clients.id), NOT NULL | ✓ |
| `report_type` | VARCHAR(30) | CHECK IN ('large_cash_transaction', 'suspicious_transaction', 'terrorist_property'), NOT NULL | ✓ |
| `amount` | NUMERIC(15, 2) | NOT NULL (Decimal) | ✓ |
| `currency` | VARCHAR(3) | NOT NULL, default='CAD' | ✓ |
| `transaction_date` | DATE | NOT NULL | ✓ |
| `report_date` | TIMESTAMP | NOT NULL, default=now() | ✓ |
| `submitted_to_fintrac_at` | TIMESTAMP | NULL | ✓ |
| `fintrac_reference_number` | VARCHAR(100) | NULL, UNIQUE | ✓ |
| `created_by` | UUID | FOREIGN KEY (users.id), NOT NULL | ✓ |
| `created_at` | TIMESTAMP | NOT NULL, default=now() | - |
| `updated_at` | TIMESTAMP | NOT NULL, default=now(), onupdate=now() | - |
| `deleted_at` | TIMESTAMP | NULL (soft delete) | ✓ |

**Indexes:**
```sql
CREATE INDEX idx_frep_app_type ON fintrac_reports(application_id, report_type);
CREATE INDEX idx_frep_date_amount ON fintrac_reports(transaction_date, amount);
CREATE INDEX idx_frep_currency_amount ON fintrac_reports(currency, amount);
CREATE INDEX idx_frep_structuring_lookup ON fintrac_reports(client_id, transaction_date) 
  WHERE report_type = 'large_cash_transaction';
```

**Relationships:**
- Many-to-one with `applications` (ON DELETE RESTRICT)
- Many-to-one with `clients` (ON DELETE RESTRICT)
- Many-to-one with `users` (created_by) (ON DELETE RESTRICT)

---

### `fintrac_pep_hio_watchlist` Table (for PEP/HIO integration)

**Table Name:** `fintrac_pep_hio_watchlist`

**Columns:**
| Column Name | Type | Constraints | Index |
|-------------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | - |
| `individual_name` | VARCHAR(255) | NOT NULL | ✓ |
| `date_of_birth` | DATE | NULL (hashed for lookup) | ✓ |
| `entity_type` | VARCHAR(10) | CHECK IN ('pep', 'hio'), NOT NULL | ✓ |
| `source_list` | VARCHAR(100) | NOT NULL | - |
| `added_at` | TIMESTAMP | NOT NULL, default=now() | ✓ |
| `last_updated` | TIMESTAMP | NOT NULL, default=now() | - |
| `active` | BOOLEAN | NOT NULL, default=true | ✓ |

**Indexes:**
```sql
CREATE INDEX idx_watchlist_name_dob ON fintrac_pep_hio_watchlist(individual_name, date_of_birth) 
  WHERE active = true;
CREATE INDEX idx_watchlist_type ON fintrac_pep_hio_watchlist(entity_type);
```

---

## 3. Business Logic

### Identity Verification Algorithm

```python
# Risk Scoring Calculation
def calculate_risk_score(verification: dict) -> tuple[str, list[str]]:
    """
    Returns risk_level and list of risk factors
    """
    score = 0
    factors = []
    
    # Base score by method
    if verification['method'] == 'in_person':
        score -= 10
    elif verification['method'] == 'credit_file':
        score += 5
        factors.append("credit_file_verification")
    elif verification['method'] == 'dual_process':
        score -= 5
    
    # PEP/HIO flags
    if verification['is_pep']:
        score += 30
        factors.append("pep_flag")
    if verification['is_hio']:
        score += 25
        factors.append("hio_flag")
    
    # Province risk (example: high-risk provinces)
    high_risk_provinces = ['ON', 'BC']  # Configurable
    if verification['issuing_province'] in high_risk_provinces:
        score += 10
        factors.append("high_risk_province")
    
    # ID expiry proximity
    days_to_expiry = (verification['id_expiry_date'] - date.today()).days
    if days_to_expiry < 30:
        score += 15
        factors.append("id_near_expiry")
    
    # Determine level
    if score < 0:
        return "low", factors
    elif score <= 20:
        return "medium", factors
    else:
        return "high", factors

# Enhanced Due Diligence Check
def requires_enhanced_due_diligence(risk_level: str, is_pep: bool, is_hio: bool) -> bool:
    return risk_level == "high" or is_pep or is_hio
```

### Structuring Detection Algorithm

```python
# Check for multiple transactions below threshold within 24h
async def detect_structuring(
    client_id: UUID, 
    current_amount: Decimal, 
    transaction_date: date,
    db_session
) -> bool:
    """
    Returns True if structuring pattern detected
    """
    twenty_four_hours_ago = transaction_date - timedelta(hours=24)
    
    result = await db_session.execute(
        select(func.sum(fintrac_reports.c.amount))
        .where(
            fintrac_reports.c.client_id == client_id,
            fintrac_reports.c.transaction_date >= twenty_four_hours_ago,
            fintrac_reports.c.report_type == "large_cash_transaction",
            fintrac_reports.c.deleted_at.is_(None)
        )
    )
    
    total = result.scalar() or Decimal('0')
    total += current_amount
    
    # If total exceeds threshold, flag as structuring
    return total > Decimal('10000')
```

### Transaction Reporting State Machine

```
report_created -> pending_submission -> submitted_to_fintrac -> acknowledged
      |                |                      |                    |
      |                |-> submission_failed--|                    |
      |                |                      |-> fintrac_rejected |
      |--> cancelled (admin only)            |-> fintrac_accepted |
```

**Transitions:**
- `report_created → pending_submission`: Automatic on creation
- `pending_submission → submitted_to_fintrac`: On successful API call
- `pending_submission → submission_failed`: On API failure (retryable)
- `submitted_to_fintrac → acknowledged`: On FINTRAC confirmation
- Any state → cancelled: Admin action only (soft delete)

### Risk Assessment Aggregation

```python
# Calculate overall client risk across all applications
async def get_client_risk_assessment(client_id: UUID, db_session) -> dict:
    """
    Returns aggregated risk metrics for a client
    """
    # Get latest verification
    latest_verification = await db_session.execute(
        select(fintrac_verifications)
        .where(
            fintrac_verifications.c.client_id == client_id,
            fintrac_verifications.c.deleted_at.is_(None)
        )
        .order_by(fintrac_verifications.c.verified_at.desc())
    )
    
    if not latest_verification:
        return {"error": "No verification found"}
    
    ver = latest_verification.scalar()
    
    # Count open reports
    open_reports = await db_session.execute(
        select(func.count())
        .where(
            fintrac_reports.c.client_id == client_id,
            fintrac_reports.c.submitted_to_fintrac_at.is_(None),
            fintrac_reports.c.deleted_at.is_(None)
        )
    )
    
    # Determine overall risk
    risk_factors = []
    if ver.is_pep: risk_factors.append("pep")
    if ver.is_hio: risk_factors.append("hio")
    if ver.risk_level == "high": risk_factors.append("high_risk_verification")
    
    return {
        "overall_risk_level": ver.risk_level,
        "risk_factors": risk_factors,
        "pep_status": ver.is_pep,
        "hio_status": ver.is_hio,
        "open_reports_count": open_reports.scalar()
    }
```

---

## 4. Migrations

### Alembic Revision: `create_fintrac_tables`

**New Tables:**
```sql
-- fintrac_verifications
CREATE TABLE fintrac_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    verification_method VARCHAR(20) NOT NULL CHECK (verification_method IN ('in_person', 'credit_file', 'dual_process')),
    id_type VARCHAR(50) NOT NULL,
    id_number_encrypted BYTEA NOT NULL,
    id_expiry_date DATE NOT NULL,
    id_issuing_province VARCHAR(2) NOT NULL,
    verified_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    verified_at TIMESTAMP NOT NULL DEFAULT now(),
    is_pep BOOLEAN NOT NULL DEFAULT false,
    is_hio BOOLEAN NOT NULL DEFAULT false,
    risk_level VARCHAR(10) NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    record_created_at TIMESTAMP NOT NULL DEFAULT now(),
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    deleted_at TIMESTAMP
);

-- fintrac_reports
CREATE TABLE fintrac_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    report_type VARCHAR(30) NOT NULL CHECK (report_type IN ('large_cash_transaction', 'suspicious_transaction', 'terrorist_property')),
    amount NUMERIC(15, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'CAD',
    transaction_date DATE NOT NULL,
    report_date TIMESTAMP NOT NULL DEFAULT now(),
    submitted_to_fintrac_at TIMESTAMP,
    fintrac_reference_number VARCHAR(100) UNIQUE,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    deleted_at TIMESTAMP
);

-- fintrac_pep_hio_watchlist (for automated PEP/HIO checks)
CREATE TABLE fintrac_pep_hio_watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    individual_name VARCHAR(255) NOT NULL,
    date_of_birth_hash VARCHAR(64), -- SHA256 hash for privacy
    entity_type VARCHAR(10) NOT NULL CHECK (entity_type IN ('pep', 'hio')),
    source_list VARCHAR(100) NOT NULL,
    added_at TIMESTAMP NOT NULL DEFAULT now(),
    last_updated TIMESTAMP NOT NULL DEFAULT now(),
    active BOOLEAN NOT NULL DEFAULT true
);
```

**Indexes:**
```sql
-- fintrac_verifications indexes
CREATE INDEX idx_finv_app_client ON fintrac_verifications(application_id, client_id);
CREATE INDEX idx_finv_client_verified_desc ON fintrac_verifications(client_id, verified_at DESC);
CREATE INDEX idx_finv_risk_flags ON fintrac_verifications(risk_level, is_pep, is_hio) 
  WHERE risk_level = 'high' OR is_pep = true OR is_hio = true;
CREATE INDEX idx_finv_province_expiry ON fintrac_verifications(id_issuing_province, id_expiry_date);
CREATE INDEX idx_finv_deleted_at ON fintrac_verifications(deleted_at) WHERE deleted_at IS NOT NULL;

-- fintrac_reports indexes
CREATE INDEX idx_frep_app_type ON fintrac_reports(application_id, report_type);
CREATE INDEX idx_frep_date_amount ON fintrac_reports(transaction_date, amount);
CREATE INDEX idx_frep_currency_amount ON fintrac_reports(currency, amount);
CREATE INDEX idx_frep_structuring_lookup ON fintrac_reports(client_id, transaction_date) 
  WHERE report_type = 'large_cash_transaction' AND deleted_at IS NULL;
CREATE INDEX idx_frep_submitted_at ON fintrac_reports(submitted_to_fintrac_at) WHERE submitted_to_fintrac_at IS NULL;
CREATE INDEX idx_frep_deleted_at ON fintrac_reports(deleted_at) WHERE deleted_at IS NOT NULL;

-- watchlist indexes
CREATE INDEX idx_watchlist_name_hash ON fintrac_pep_hio_watchlist(individual_name, date_of_birth_hash) 
  WHERE active = true;
CREATE INDEX idx_watchlist_type ON fintrac_pep_hio_watchlist(entity_type);
```

**Data Migration:**
- None required for new tables
- **WARNING:** If migrating from legacy system, existing verification data must be encrypted and backfilled. This requires a separate secure migration script that processes PII in memory only.

---

## 5. Security & Compliance

### PIPEDA Compliance
- **Encryption at Rest:** `id_number_encrypted` uses AES-256-GCM via `common/security.encrypt_pii()` with key rotation every 90 days
- **Data Minimization:** Only collect ID number, expiry, and province—no full address or additional PII
- **Access Logging:** All access to verification records logged with `correlation_id` and `user_id`; PII never logged
- **PII Handling:** ID numbers are decrypted only in-memory for FINTRAC reporting; never serialized to JSON logs

### FINTRAC Compliance
- **Universal Verification:** All clients verified regardless of mortgage amount (enforced at application submission)
- **Large Cash Transaction Reporting:** Automatic flagging when `amount > CAD $10,000` and `currency = 'CAD'` (foreign currency converted using daily Bank of Canada rate)
- **Structuring Detection:** Hourly cron job runs `detect_structuring()` algorithm; flags suspicious patterns and auto-creates `suspicious_transaction` report
- **Retention:** Soft-delete only; `deleted_at` column prevents hard deletion. Annual audit query verifies no hard deletes:
  ```sql
  SELECT * FROM fintrac_reports WHERE NOT EXISTS IN (SELECT * FROM pg_xact_commit_timestamp(xmin));
  ```
- **Submission Timeline:** 
  - Large Cash: Submitted within 15 days of transaction
  - Suspicious: Submitted within 24 hours of detection
  - Terrorist Property: Immediate submission (< 2 hours)

### OSFI B-20
- **Not Directly Applicable:** FINTRAC module does not calculate GDS/TDS ratios. However, must ensure FINTRAC compliance checks do not introduce latency that could affect stress test calculations in the underwriting module.

### CMHC
- **Not Applicable:** No insurance premium calculations in this module

### Authentication & Authorization
- **JWT Required:** All endpoints require valid JWT token via `common/security.verify_token()`
- **Role-Based Access Control:**
  - `underwriter`: CREATE verification, CREATE report, READ all
  - `admin`: Full access including soft-delete
  - `auditor`: READ-only access
  - `system`: Internal service account for cron jobs
- **mTLS:** FINTRAC API submissions use mutual TLS authentication with certificate stored in HashiCorp Vault

### PEP/HIO List Integration
- **Automated Sync:** Daily cron job at 02:00 UTC fetches updates from FINTRAC watchlist API
- **Hash-Based Lookup:** `date_of_birth` stored as SHA256 hash for privacy-preserving matches
- **False Positive Handling:** Manual review queue for potential matches; match confidence score logged

---

## 6. Error Codes & HTTP Responses

**Module Identifier:** `FINTRAC`

| Exception Class | HTTP Status | Error Code | Message Pattern | Retryable |
|-----------------|-------------|------------|-----------------|-----------|
| `FintracVerificationNotFoundError` | 404 | `FINTRAC_001` | "Verification record not found for client {client_id}" | No |
| `FintracApplicationNotFoundError` | 404 | `FINTRAC_002` | "Application {application_id} not found" | No |
| `FintracClientNotFoundError` | 404 | `FINTRAC_003` | "Client {client_id} not found" | No |
| `FintracValidationError` | 422 | `FINTRAC_004` | "{field_name}: {validation_message}" | No |
| `FintracStructuringDetectedError` | 409 | `FINTRAC_005` | "Structuring pattern detected: {detail}" | No |
| `FintracInsufficientPermissionsError` | 403 | `FINTRAC_006` | "Insufficient permissions for {action}" | No |
| `FintracEnhancedDueDiligenceError` | 409 | `FINTRAC_007` | "Enhanced due diligence required: {reason}" | No |
| `FintracSubmissionError` | 502 | `FINTRAC_008` | "FINTRAC API submission failed: {detail}" | Yes |
| `FintracRateLimitError` | 429 | `FINTRAC_009` | "FINTRAC API rate limit exceeded" | Yes |

### Error Response Format
All errors return JSON with consistent structure:
```json
{
  "detail": "Verification record not found for client 123e4567-e89b-12d3-a456-426614174000",
  "error_code": "FINTRAC_001",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2024-01-15T14:30:00Z",
  "request_id": "req_abc123"
}
```

### Specific Edge Cases
- **Expired ID:** `POST /verify-identity` returns `FINTRAC_004` if `id_expiry_date < today()`
- **Structuring Threshold:** If client has 3 transactions of $4,000 within 24h, `FINTRAC_005` triggered
- **Duplicate Report:** Attempting to report same transaction twice returns `FINTRAC_004` with "Duplicate transaction detected"
- **FINTRAC API Timeout:** After 3 retries with exponential backoff, returns `FINTRAC_008` (retryable)
- **Missing Encryption Key:** Returns `500 Internal Server Error` with `FINTRAC_010` (internal code, not exposed to client)

### Logging Requirements
- **NEVER log:** `id_number` (plain text), SIN, DOB, or any decrypted PII
- **ALWAYS log:** `correlation_id`, `user_id`, `verification_id`, `report_id`, `error_code`
- **Audit log entries** written to separate `audit_logs` table with 7-year retention

---

## WARNING: Missing Critical Context

The following details are required for production implementation but were not provided in requirements:

1. **PEP/HIO List Source:** Official data source URL and update frequency (FINTRAC vs third-party)
2. **FINTRAC API Spec:** Authentication method, endpoint URLs, rate limits, and response schemas
3. **Risk Score Weights:** Exact point values and thresholds need regulatory approval
4. **Currency Conversion:** Exchange rate API for non-CAD transactions
5. **Alerting:** Notification mechanism for high-risk verifications (email, Slack, PagerDuty)
6. **Backup Strategy:** 5-year retention requires immutable backups (WORM storage)
7. **Disaster Recovery:** RTO/RPO targets for FINTRAC reporting system

**Recommendation:** Create follow-up design spike documents for each missing area before implementation.