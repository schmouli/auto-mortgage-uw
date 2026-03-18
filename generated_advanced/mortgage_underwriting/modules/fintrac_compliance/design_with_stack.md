# Design: FINTRAC Compliance
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# FINTRAC Compliance Module Design

**Design Document Location:** `docs/design/fintrac-compliance.md`  
**Module Identifier:** FINTRAC  
**Last Updated:** 2024-01-15  
**Compliance Frameworks:** FINTRAC PCMLTFA, PIPEDA, OSFI B-20 (indirect)

---

## 1. Endpoints

### 1.1 POST /api/v1/fintrac/applications/{id}/verify-identity
Submit identity verification record for a mortgage application client.

**Authentication:** JWT required (underwriter or compliance officer role)  
**Authorization:** `fintrac:write` scope

**Request Body Schema:**
```python
class FintracVerificationRequest(BaseModel):
    client_id: UUID  # FK to clients table
    verification_method: Literal["in_person", "credit_file", "dual_process"]
    id_type: Literal["passport", "drivers_license", "provincial_id", "certificate_of_citizenship"]
    id_number: str  # Plaintext; encrypted before storage
    id_expiry_date: date
    id_issuing_province: str  # 2-letter province code
    is_pep: bool = False
    is_hio: bool = False
    risk_level: Literal["low", "medium", "high"] = "low"
    
    # Optional enhanced due diligence fields
    source_of_funds: Optional[str] = None
    occupation: Optional[str] = None
    employer: Optional[str] = None
```

**Response Schema (201 Created):**
```python
class FintracVerificationResponse(BaseModel):
    verification_id: UUID
    application_id: UUID
    client_id: UUID
    verification_method: str
    id_type: str
    id_expiry_date: date
    id_issuing_province: str
    verified_by: UUID  # User ID from JWT
    verified_at: datetime
    is_pep: bool
    is_hio: bool
    risk_level: str
    requires_enhanced_due_diligence: bool  # Computed: true if high risk, PEP, or HIO
    created_at: datetime
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 400 | FINTRAC_001 | "Application {id} not in eligible state for verification" | Application status not in [submitted, underwriting] |
| 401 | AUTH_001 | "Invalid or expired token" | JWT validation failure |
| 403 | AUTH_002 | "Insufficient permissions" | Missing `fintrac:write` scope |
| 404 | FINTRAC_002 | "Application {id} not found" | Application ID doesn't exist |
| 422 | FINTRAC_003 | "id_number: encryption failed" | PII encryption service error |
| 422 | FINTRAC_004 | "id_expiry_date: cannot be in the past" | Expired ID document |
| 422 | FINTRAC_005 | "dual_process method requires credit_file reference" | Missing required credit reference |

---

### 1.2 GET /api/v1/fintrac/applications/{id}/verification
Retrieve identity verification status for an application.

**Authentication:** JWT required (underwriter, compliance officer, or auditor role)  
**Authorization:** `fintrac:read` scope

**Response Schema (200 OK):**
```python
class FintracVerificationStatusResponse(BaseModel):
    verification_id: UUID
    application_id: UUID
    client_id: UUID
    verification_status: Literal["pending", "verified", "enhanced_due_diligence_required", "failed"]
    verified_at: datetime
    verified_by: Optional[UUID]
    risk_level: str
    requires_enhanced_due_diligence: bool
    enhanced_due_diligence_status: Optional[Literal["pending", "completed", "escalated"]]
    fintrac_compliant: bool  # True if verification_method meets FINTRAC requirements
    created_at: datetime
    # Note: id_number and PII fields excluded from response per PIPEDA
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 401 | AUTH_001 | "Invalid or expired token" | JWT validation failure |
| 403 | AUTH_002 | "Insufficient permissions" | Missing `fintrac:read` scope |
| 404 | FINTRAC_006 | "Verification record not found for application {id}" | No verification submitted |

---

### 1.3 POST /api/v1/fintrac/applications/{id}/report-transaction
File a FINTRAC report (large cash, suspicious, or terrorist property).

**Authentication:** JWT required (compliance officer role only)  
**Authorization:** `fintrac:report:file` scope

**Request Body Schema:**
```python
class FintracReportRequest(BaseModel):
    report_type: Literal["large_cash_transaction", "suspicious_transaction", "terrorist_property"]
    amount: Decimal  # Must be > 10000 CAD for large_cash_transaction
    currency: str = "CAD"  # ISO 4217 code; auto-converted to CAD if different
    transaction_date: datetime
    transaction_location: Optional[str] = None  # Branch location for in-person
    third_party_details: Optional[dict] = None  # Name, address if applicable
    suspicious_indicators: List[str] = []  # FINTRAC indicator codes
    narrative: Optional[str] = None  # Free-text description for STRs
```

**Response Schema (202 Accepted):**
```python
class FintracReportResponse(BaseModel):
    report_id: UUID
    application_id: UUID
    report_type: str
    amount_cad: Decimal  # Converted and rounded to 2 decimals
    currency: str
    transaction_date: datetime
    report_date: datetime
    submitted_to_fintrac_at: Optional[datetime]  # Null until successfully submitted
    fintrac_reference_number: Optional[str]
    status: Literal["draft", "submitted", "acknowledged", "rejected"]
    created_by: UUID
    created_at: datetime
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 400 | FINTRAC_007 | "Large cash transaction threshold not met: {amount} CAD" | Amount ≤ 10000 CAD for LCTR |
| 400 | FINTRAC_008 | "Suspicious transaction report requires narrative" | Missing narrative for STR |
| 401 | AUTH_001 | "Invalid or expired token" | JWT validation failure |
| 403 | AUTH_003 | "Compliance officer role required" | Missing required role |
| 404 | FINTRAC_009 | "Application {id} not found" | Application ID doesn't exist |
| 422 | FINTRAC_010 | "currency: unsupported currency code" | Non-ISO 4217 currency |
| 422 | FINTRAC_011 | "suspicious_indicators: invalid code STR-001" | Unknown indicator code |

---

### 1.4 GET /api/v1/fintrac/applications/{id}/reports
List all FINTRAC reports filed for an application.

**Authentication:** JWT required (compliance officer or auditor role)  
**Authorization:** `fintrac:report:read` scope

**Query Parameters:**
- `report_type` (optional): Filter by report type
- `date_from`, `date_to` (optional): Filter by transaction date range
- `status` (optional): Filter by submission status

**Response Schema (200 OK):**
```python
class FintracReportListResponse(BaseModel):
    application_id: UUID
    reports: List[FintracReportSummary]
    total_count: int

class FintracReportSummary(BaseModel):
    report_id: UUID
    report_type: str
    amount_cad: Decimal
    transaction_date: date
    status: str
    fintrac_reference_number: Optional[str]
    created_at: datetime
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 401 | AUTH_001 | "Invalid or expired token" | JWT validation failure |
| 403 | AUTH_002 | "Insufficient permissions" | Missing required scope |
| 404 | FINTRAC_012 | "Application {id} not found" | Application ID doesn't exist |

---

### 1.5 GET /api/v1/fintrac/risk-assessment/{client_id}
Get consolidated risk assessment for a client across all applications.

**Authentication:** JWT required (underwriter or compliance officer role)  
**Authorization:** `fintrac:risk:read` scope

**Response Schema (200 OK):**
```python
class ClientRiskAssessmentResponse(BaseModel):
    client_id: UUID
    overall_risk_score: Decimal  # 0.0 to 100.0
    risk_level: Literal["low", "medium", "high"]
    factors: List[RiskFactor]
    applications_with_reports: int
    total_reports_filed: int
    last_verification_date: Optional[datetime]
    pep_status: bool
    hio_status: bool
    enhanced_due_diligence_count: int
    created_at: datetime

class RiskFactor(BaseModel):
    factor_type: str  # e.g., "pep_status", "geographic_risk", "transaction_pattern"
    weight: Decimal
    score: Decimal
    description: str
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 401 | AUTH_001 | "Invalid or expired token" | JWT validation failure |
| 403 | AUTH_002 | "Insufficient permissions" | Missing required scope |
| 404 | FINTRAC_013 | "Client {client_id} not found" | Client ID doesn't exist |

---

## 2. Models & Database

### 2.1 `fintrac_verifications` Table

**Table Name:** `fintrac_verifications`  
**Description:** Stores identity verification records per FINTRAC PCMLTFA requirements. Records are **immutable** after creation for audit trail compliance.

| Column Name | Type | Constraints | Index | Encrypted | Notes |
|-------------|------|-------------|-------|-----------|-------|
| `id` | `UUID` | PRIMARY KEY, default gen_random_uuid() | - | No | Surrogate key |
| `application_id` | `UUID` | NOT NULL, FK(applications.id) | IX_app_id | No | - |
| `client_id` | `UUID` | NOT NULL, FK(clients.id) | IX_client_id | No | - |
| `verification_method` | `VARCHAR(20)` | NOT NULL, CHECK in ('in_person','credit_file','dual_process') | IX_method | No | FINTRAC method |
| `id_type` | `VARCHAR(50)` | NOT NULL | - | No | Document type |
| `id_number_encrypted` | `BYTEA` | NOT NULL | - | **Yes** | AES-256 encrypted |
| `id_number_hash` | `VARCHAR(64)` | NOT NULL, UNIQUE | IX_hash | No | SHA-256 for lookups |
| `id_expiry_date` | `DATE` | NOT NULL | - | No | Document expiry |
| `id_issuing_province` | `VARCHAR(2)` | NOT NULL, CHECK length=2 | IX_province | No | Province code |
| `verified_by` | `UUID` | NOT NULL, FK(users.id) | IX_verified_by | No | Underwriter ID |
| `verified_at` | `TIMESTAMP` | NOT NULL, default now() | IX_verified_at | No | Verification timestamp |
| `is_pep` | `BOOLEAN` | NOT NULL, default false | IX_pep | No | Politically exposed person |
| `is_hio` | `BOOLEAN` | NOT NULL, default false | IX_hio | No | Head of international org |
| `risk_level` | `VARCHAR(10)` | NOT NULL, default 'low' | IX_risk | No | low/medium/high |
| `source_of_funds` | `TEXT` | NULL | - | No | EDD field |
| `occupation` | `VARCHAR(100)` | NULL | - | No | EDD field |
| `employer` | `VARCHAR(100)` | NULL | - | No | EDD field |
| `created_at` | `TIMESTAMP` | NOT NULL, default now() | IX_created_at | No | Audit field |
| `updated_at` | `TIMESTAMP` | NULL | IX_updated_at | No | **Only for admin metadata** |

**Indexes:**
- `IX_fintrac_verifications_app_client` (application_id, client_id) - Composite for app-level queries
- `IX_fintrac_verifications_risk_pep_hio` (risk_level, is_pep, is_hio) - EDD screening
- `IX_fintrac_verifications_verified_at` (verified_at DESC) - Time-based audits

**Relationships:**
- Many-to-one: `application_id` → `applications.id`
- Many-to-one: `client_id` → `clients.id`
- Many-to-one: `verified_by` → `users.id`

**Compliance Notes:**
- `id_number_encrypted` uses `encrypt_pii()` from `common/security.py` (AES-256-GCM)
- `id_number_hash` used for duplicate detection without revealing PII
- No `deleted_at` column: FINTRAC records **never deleted** per 5-year retention rule

---

### 2.2 `fintrac_reports` Table

**Table Name:** `fintrac_reports`  
**Description:** Stores FINTRAC filed reports (LCTR, STR, TPFR). **Append-only, immutable** after submission acknowledgment.

| Column Name | Type | Constraints | Index | Encrypted | Notes |
|-------------|------|-------------|-------|-----------|-------|
| `id` | `UUID` | PRIMARY KEY, default gen_random_uuid() | - | No | Surrogate key |
| `application_id` | `UUID` | NOT NULL, FK(applications.id) | IX_app_id | No | - |
| `report_type` | `VARCHAR(30)` | NOT NULL, CHECK in ('large_cash_transaction','suspicious_transaction','terrorist_property') | IX_type | No | FINTRAC report type |
| `amount` | `NUMERIC(15,2)` | NOT NULL | IX_amount | No | Original amount |
| `currency` | `VARCHAR(3)` | NOT NULL, default 'CAD' | - | No | ISO 4217 code |
| `amount_cad` | `NUMERIC(15,2)` | NOT NULL | IX_amount_cad | No | Converted to CAD |
| `transaction_date` | `TIMESTAMP` | NOT NULL | IX_txn_date | No | Actual transaction date |
| `report_date` | `TIMESTAMP` | NOT NULL, default now() | IX_report_date | No | Report creation date |
| `submitted_to_fintrac_at` | `TIMESTAMP` | NULL | IX_submitted_at | No | Successful submission timestamp |
| `fintrac_reference_number` | `VARCHAR(50)` | NULL | IX_ref_num | No | FINTRAC ACK number |
| `status` | `VARCHAR(20)` | NOT NULL, default 'draft' | IX_status | No | draft/submitted/acknowledged/rejected |
| `transaction_location` | `VARCHAR(100)` | NULL | - | No | Branch/location |
| `third_party_details` | `JSONB` | NULL | - | **Partial** | Encrypted if contains PII |
| `suspicious_indicators` | `JSONB` | NULL | - | No | Array of FINTRAC codes |
| `narrative` | `TEXT` | NULL | - | No | STR narrative |
| `created_by` | `UUID` | NOT NULL, FK(users.id) | IX_created_by | No | Compliance officer |
| `created_at` | `TIMESTAMP` | NOT NULL, default now() | IX_created_at | No | Audit field |
| `updated_at` | `TIMESTAMP` | NULL | - | No | **Status transitions only** |

**Indexes:**
- `IX_fintrac_reports_app_type_date` (application_id, report_type, transaction_date DESC) - App report history
- `IX_fintrac_reports_status_submitted` (status, submitted_to_fintrac_at) - Pending submissions
- `IX_fintrac_reports_txn_date_amount` (transaction_date, amount_cad) - Threshold monitoring
- `IX_fintrac_reports_fintrac_ref` (fintrac_reference_number) - FINTRAC lookup

**Relationships:**
- Many-to-one: `application_id` → `applications.id`
- Many-to-one: `created_by` → `users.id`

**Compliance Notes:**
- `third_party_details` encrypted if contains names/addresses (PIPEDA)
- `status` transitions logged in `fintrac_report_audit_log` (separate audit table for immutability)
- `amount` and `amount_cad` use `Decimal` type (no float precision loss)

---

### 2.3 `fintrac_pep_hio_registry` Table (Supporting)

**Table Name:** `fintrac_pep_hio_registry`  
**Description:** Cached PEP/HIO list from FINTRAC and international sources. Auto-updated daily.

| Column Name | Type | Constraints | Index | Notes |
|-------------|------|-------------|-------|-------|
| `id` | `UUID` | PRIMARY KEY | - | - |
| `name_hash` | `VARCHAR(64)` | NOT NULL, UNIQUE | IX_name_hash | SHA-256 of full name |
| `date_of_birth_hash` | `VARCHAR(64)` | NULL | IX_dob_hash | SHA-256 for matching |
| `pep_status` | `BOOLEAN` | NOT NULL, default false | IX_pep | - |
| `hio_status` | `BOOLEAN` | NOT NULL, default false | IX_hio | - |
| `jurisdiction` | `VARCHAR(100)` | NULL | - | Country/province |
| `source_list` | `VARCHAR(50)` | NOT NULL | - | "FINTRAC", "World Bank", etc. |
| `last_updated` | `TIMESTAMP` | NOT NULL | IX_updated | - |

---

## 3. Business Logic

### 3.1 Identity Verification Flow

**Pre-conditions:**
- Application status must be `submitted` or `underwriting`
- Client must not have existing active verification (idempotent re-verification allowed with new record)

**Process:**
1. **Validation:** Verify `id_expiry_date` > today + 30 days (grace period)
2. **PEP/HIO Check:** Query `fintrac_pep_hio_registry` using `client_id` → `name_hash` and `dob_hash`
3. **Encryption:** `id_number_encrypted = encrypt_pii(id_number)` via `common/security.py`
4. **Hashing:** `id_number_hash = sha256(id_number)` for duplicate detection
5. **Risk Determination:** 
   - If `is_pep=True` or `is_hio=True` or `risk_level='high'` → `requires_enhanced_due_diligence=True`
   - Else → `requires_enhanced_due_diligence=False`
6. **Storage:** Insert into `fintrac_verifications` (immutable record)
7. **Audit Log:** Log action with `correlation_id` (PII excluded from logs)

**FINTRAC Compliance:** Meets PCMLTFA Schedule 7 requirements for verification methods.

---

### 3.2 Risk Assessment Algorithm

**Composite Risk Score Formula:**
```
risk_score = (
    base_risk_score * 0.30 +
    geographic_risk * 0.25 +
    transaction_pattern_risk * 0.25 +
    product_risk * 0.10 +
    client_history_risk * 0.10
) * pep_hio_multiplier
```

**Factor Breakdown:**
- `base_risk_score`: 0-100 from verification `risk_level` (low=10, medium=50, high=90)
- `geographic_risk`: 0-100 based on `id_issuing_province` and property location (high-risk jurisdictions = 80+)
- `transaction_pattern_risk`: 0-100; auto-calculated from `fintrac_reports` frequency/amount (structuring patterns = 90+)
- `product_risk`: 0-100; LTV > 80% → 60, >95% → 90
- `client_history_risk`: 0-100; previous STRs = 90, multiple applications = 30
- `pep_hio_multiplier`: 2.0 if PEP or HIO, else 1.0

**Risk Level Thresholds:**
- **Low:** risk_score < 35
- **Medium:** 35 ≤ risk_score < 70
- **High:** risk_score ≥ 70

**Enhanced Due Diligence (EDD) Triggers:**
- Automatic if `risk_level='high'` OR `is_pep=True` OR `is_hio=True`
- Requires additional fields: `source_of_funds`, `occupation`, `employer`
- Must be reviewed by senior compliance officer (role=`compliance_senior`)

---

### 3.3 Transaction Monitoring & Structuring Detection

**Large Cash Transaction Rule:**
- Monitor all cash transactions via `POST /report-transaction`
- **Threshold:** `amount_cad > 10000.00`
- **Currency Conversion:** Use Bank of Canada daily exchange rate (cached in `exchange_rates` table)
- **Auto-flagging:** If `amount_cad > 10000`, set `status='draft'` and notify compliance team

**Structuring Detection Algorithm:**
- Scan `fintrac_reports` for same `application_id` within 24-hour window
- Count transactions where `amount_cad < 10000` and `report_type='large_cash_transaction'`
- **Flag if:** ≥ 3 transactions OR sum of transactions > 15000 within 24h
- **Action:** Create `suspicious_transaction` report automatically with `suspicious_indicators=['STR-STRUCT-001']`

**Real-time Monitoring:**
- Background worker (`celery` task) runs every 15 minutes
- Queries `transactions` table for new cash deposits
- Inserts into `fintrac_reports` with `status='draft'` if threshold met

---

### 3.4 FINTRAC Report Submission Workflow

**State Machine:**
```
draft → submitted → acknowledged
   ↓          ↓
rejected (manual review)
```

**Submission Process:**
1. **Draft Stage:** Report created via API, stored in `fintrac_reports`
2. **Validation:** Check required fields, amount thresholds, suspicious indicators
3. **Submission:** Compliance officer triggers `POST /report-transaction/{id}/submit`
4. **FINTRAC API Adapter:**
   - **Protocol:** gRPC (primary) or REST (fallback) to FINTRAC reporting gateway
   - **Auth:** mTLS with client certificate from `common/security.py`
   - **Payload:** Convert to FINTRAC XML schema v4.0
5. **Acknowledgment:** Store `fintrac_reference_number` and `submitted_to_fintrac_at` on success
6. **Retry Logic:** Exponential backoff (3 attempts) on network failures; log failures to `structlog`

**Compliance:** Meets FINTRAC Electronic Funds Transfer Report (EFTR) and Large Cash Transaction Report (LCTR) technical specifications.

---

### 3.5 Record Retention & Audit Trail

**Retention Policy:**
- All `fintrac_verifications` and `fintrac_reports` retained for **minimum 5 years** from `created_at`
- **No hard delete:** Database policy rejects DELETE operations on these tables
- **Soft delete not used:** Records remain active for audit
- **Archiving:** After 5 years, move to `fintrac_archive` schema (still queryable)

**Audit Logging:**
- All mutations logged to `fintrac_audit_log` table (separate from application logs)
- **Logged fields:** `table_name`, `record_id`, `action` (INSERT/UPDATE), `changed_by`, `changed_at`, `correlation_id`, `ip_address`
- **PII excluded:** No `id_number`, SIN, or DOB in audit logs
- **Immutability:** `fintrac_audit_log` is append-only, stored on separate PostgreSQL instance for tamper resistance

---

## 4. Migrations

### Alembic Revision: `rev_001_create_fintrac_tables.py`

**New Tables:**
```python
op.create_table(
    'fintrac_verifications',
    sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
    sa.Column('application_id', sa.UUID(), sa.ForeignKey('applications.id'), nullable=False),
    sa.Column('client_id', sa.UUID(), sa.ForeignKey('clients.id'), nullable=False),
    sa.Column('verification_method', sa.String(20), nullable=False),
    sa.Column('id_type', sa.String(50), nullable=False),
    sa.Column('id_number_encrypted', sa.LargeBinary(), nullable=False),
    sa.Column('id_number_hash', sa.String(64), nullable=False, unique=True),
    sa.Column('id_expiry_date', sa.Date(), nullable=False),
    sa.Column('id_issuing_province', sa.String(2), nullable=False),
    sa.Column('verified_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
    sa.Column('verified_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    sa.Column('is_pep', sa.Boolean(), nullable=False, server_default='false'),
    sa.Column('is_hio', sa.Boolean(), nullable=False, server_default='false'),
    sa.Column('risk_level', sa.String(10), nullable=False, server_default='low'),
    sa.Column('source_of_funds', sa.Text(), nullable=True),
    sa.Column('occupation', sa.String(100), nullable=True),
    sa.Column('employer', sa.String(100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint("verification_method IN ('in_person', 'credit_file', 'dual_process')"),
    sa.CheckConstraint("risk_level IN ('low', 'medium', 'high')"),
    sa.CheckConstraint("LENGTH(id_issuing_province) = 2")
)

op.create_table(
    'fintrac_reports',
    sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
    sa.Column('application_id', sa.UUID(), sa.ForeignKey('applications.id'), nullable=False),
    sa.Column('report_type', sa.String(30), nullable=False),
    sa.Column('amount', sa.Numeric(15, 2), nullable=False),
    sa.Column('currency', sa.String(3), nullable=False, server_default='CAD'),
    sa.Column('amount_cad', sa.Numeric(15, 2), nullable=False),
    sa.Column('transaction_date', sa.DateTime(), nullable=False),
    sa.Column('report_date', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    sa.Column('submitted_to_fintrac_at', sa.DateTime(), nullable=True),
    sa.Column('fintrac_reference_number', sa.String(50), nullable=True),
    sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
    sa.Column('transaction_location', sa.String(100), nullable=True),
    sa.Column('third_party_details', sa.JSONB(), nullable=True),
    sa.Column('suspicious_indicators', sa.JSONB(), nullable=True),
    sa.Column('narrative', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint("report_type IN ('large_cash_transaction', 'suspicious_transaction', 'terrorist_property')"),
    sa.CheckConstraint("status IN ('draft', 'submitted', 'acknowledged', 'rejected')")
)

op.create_table(
    'fintrac_pep_hio_registry',
    sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
    sa.Column('name_hash', sa.String(64), nullable=False, unique=True),
    sa.Column('date_of_birth_hash', sa.String(64), nullable=True),
    sa.Column('pep_status', sa.Boolean(), nullable=False, server_default='false'),
    sa.Column('hio_status', sa.Boolean(), nullable=False, server_default='false'),
    sa.Column('jurisdiction', sa.String(100), nullable=True),
    sa.Column('source_list', sa.String(50), nullable=False),
    sa.Column('last_updated', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
)
```

**Indexes:**
```python
# Composite indexes for common query patterns
op.create_index('ix_fintrac_verifications_app_client', 'fintrac_verifications', ['application_id', 'client_id'])
op.create_index('ix_fintrac_verifications_risk_pep_hio', 'fintrac_verifications', ['risk_level', 'is_pep', 'is_hio'])
op.create_index('ix_fintrac_verifications_id_hash', 'fintrac_verifications', ['id_number_hash'], unique=True)

op.create_index('ix_fintrac_reports_app_type_date', 'fintrac_reports', ['application_id', 'report_type', sa.text('transaction_date DESC')])
op.create_index('ix_fintrac_reports_status_submitted', 'fintrac_reports', ['status', 'submitted_to_fintrac_at'])
op.create_index('ix_fintrac_reports_txn_date_amount', 'fintrac_reports', ['transaction_date', 'amount_cad'])
op.create_index('ix_fintrac_reports_fintrac_ref', 'fintrac_reports', ['fintrac_reference_number'], unique=True)

op.create_index('ix_fintrac_pep_hio_name_hash', 'fintrac_pep_hio_registry', ['name_hash'], unique=True)
op.create_index('ix_fintrac_pep_hio_dob_hash', 'fintrac_pep_hio_registry', ['date_of_birth_hash'])
```

**Data Migration:**
- None required for initial creation
- **Future migration:** Seed `fintrac_pep_hio_registry` from FINTRAC public list (CSV import via admin CLI)

---

## 5. Security & Compliance

### 5.1 PIPEDA Data Handling

**Encryption at Rest:**
- `fintrac_verifications.id_number_encrypted`: AES-256-GCM encryption via `common/security.encrypt_pii()`
- `fintrac_reports.third_party_details`: Encrypted if contains names/addresses (JSON field-level encryption)
- Encryption keys rotated every 90 days via `common/security.rotate_keys()`

**Data Minimization:**
- No SIN or DOB stored in `fintrac_*` tables (handled in separate `clients` module with encryption)
- API responses exclude `id_number_encrypted` and `id_number_hash`
- Logs **never** contain PII: `id_number`, `third_party_details`, or client names

**Access Logging:**
- All endpoint access logged with `correlation_id`, `user_id`, `client_id` (hashed), `timestamp`
- Log retention: 2 years in `structlog` JSON format, shipped to SIEM

### 5.2 FINTRAC PCMLTFA Compliance

**Identity Verification (Schedule 7):**
- `verification_method` must be one of: in-person, credit file, dual process
- `id_type` restricted to government-issued photo ID or credit file equivalent
- Records retained for 5 years from mortgage discharge date

**Large Cash Transaction Reports (LCTR):**
- Filed within 15 days of transaction (business logic enforces deadline)
- Amount threshold: **> CAD $10,000** (strictly enforced)
- Structuring detection runs every 15 minutes via Celery beat

**Suspicious Transaction Reports (STR):**
- Filed within 30 days of detection
- Requires `narrative` and `suspicious_indicators` from FINTRAC list
- Auto-generated for structuring patterns

**Record Keeping:**
- **Immutable storage:** PostgreSQL `REJECT` policy on DELETE
- **5-year retention:** Automated archive after 5 years to `fintrac_archive` schema
- **Audit trail:** Separate `fintrac_audit_log` table with tamper-proof signatures

### 5.3 OSFI B-20 Considerations

**Indirect Impact:** FINTRAC risk assessment feeds into overall mortgage risk rating used by underwriting module for GDS/TDS stress test calculations. High FINTRAC risk may trigger:
- Lower maximum LTV (e.g., 75% instead of 80%)
- Additional income verification requirements
- Higher qualifying_rate buffer (+0.25%)

### 5.4 Authentication & Authorization

**JWT Claims Required:**
- `sub`: User ID (must match `verified_by` or `created_by`)
- `scope`: Must include endpoint-specific scope (e.g., `fintrac:write`)
- `roles`: Array containing one of: `underwriter`, `compliance_officer`, `compliance_senior`, `auditor`

**mTLS for FINTRAC API:**
- Client certificate stored in Vault, rotated every 60 days
- Certificate fingerprint logged for non-repudiation

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy

```python
# In modules/fintrac/exceptions.py
class FintracException(AppException):
    """Base exception for FINTRAC module"""
    module_code = "FINTRAC"

class FintracVerificationNotFoundError(FintracException):
    """Raised when verification record is missing"""
    http_status = 404
    error_code = "FINTRAC_002"
    message_template = "Verification not found for application {application_id}"

class FintracReportNotFoundError(FintracException):
    """Raised when report ID is invalid"""
    http_status = 404
    error_code = "FINTRAC_012"
    message_template = "FINTRAC report {report_id} not found"

class FintracValidationError(FintracException):
    """Raised when input fails business rule validation"""
    http_status = 422
    error_code = "FINTRAC_003"
    message_template = "{field}: {reason}"

class FintracBusinessRuleError(FintracException):
    """Raised when FINTRAC rule is violated (e.g., threshold)"""
    http_status = 409
    error_code = "FINTRAC_007"
    message_template = "Business rule violated: {rule}"

class FintracEncryptionError(FintracException):
    """Raised when PII encryption fails"""
    http_status = 422
    error_code = "FINTRAC_003"
    message_template = "Encryption failed for {field}"

class FintracSubmissionError(FintracException):
    """Raised when FINTRAC API submission fails"""
    http_status = 502
    error_code = "FINTRAC_020"
    message_template = "FINTRAC gateway error: {detail}"

class FintracRiskAssessmentError(FintracException):
    """Raised when risk scoring calculation fails"""
    http_status = 500
    error_code = "FINTRAC_013"
    message_template = "Risk assessment failed for client {client_id}"
```

### Error Response Format

All errors return structured JSON:
```json
{
  "detail": "Verification not found for application 123e4567-e89b-12d3-a456-426614174000",
  "error_code": "FINTRAC_002",
  "module": "fintrac",
  "timestamp": "2024-01-15T14:30:00Z",
  "correlation_id": "corr_01hqn9f1k2j3g4h5i6j7k8l9m0",
  "request_id": "req_abc123def456"
}
```

### Retry and Circuit Breaker

- **FINTRAC API:** 3 retries with exponential backoff (1s, 2s, 4s)
- **Circuit breaker:** Opens after 5 consecutive failures, half-open after 60s
- **Fallback:** Queue to `fintrac_pending_submissions` table for manual retry

---

## 7. Missing Details Resolution

### 7.1 PEP/HIO List Integration
- **Source:** FINTRAC public list (weekly update), World Bank PEP list (monthly)
- **Update Mechanism:** Celery beat task `@shared_task` running every 24h at 02:00 UTC
- **Implementation:** `services.py::update_pep_hio_registry()` fetches CSV, hashes names/DOBs, upserts to `fintrac_pep_hio_registry`
- **Conflict Resolution:** If source lists conflict, prioritize FINTRAC over international sources

### 7.2 Risk Scoring Algorithm Weights
- **Configuration:** Stored in `common/config.py` as `FINTRAC_RISK_WEIGHTS` (Pydantic settings)
- **Tuning:** Compliance team can adjust weights via admin endpoint `POST /api/v1/admin/fintrac/risk-weights` (requires `admin:fintrac` scope)
- **Versioning:** Weights versioned in `risk_model_versions` table; audit trail of changes

### 7.3 FINTRAC Submission API Integration
- **Adapter Pattern:** `FintracSubmissionAdapter` abstract base class in `services.py`
- **Implementations:**
  - `FintracGrpcAdapter`: gRPC to FINTRAC v2.1 gateway (production)
  - `FintracRestAdapter`: REST fallback for disaster recovery
- **Configuration:** `FINTRAC_GATEWAY_ENDPOINT`, `FINTRAC_CLIENT_CERT`, `FINTRAC_API_KEY` in Vault
- **Timeout:** 30s per request; async submission with callback webhook

### 7.4 Transaction Monitoring Threshold Tuning
- **Thresholds Config:** `FINTRAC_LCTR_THRESHOLD=Decimal('10000.00')` in `common/config.py`
- **Structuring Params:** `FINTRAC_STRUCTURING_COUNT=3`, `FINTRAC_STRUCTURING_WINDOW=timedelta(hours=24)`, `FINTRAC_STRUCTURING_SUM=Decimal('15000.00')`
- **Override:** Compliance officer can adjust per application via `POST /api/v1/fintrac/applications/{id}/monitoring-config` (requires justification field, logged)

### 7.5 Audit Trail Requirements
- **Separate Audit DB:** `fintrac_audit_log` stored on isolated PostgreSQL instance with `pg_audit` extension enabled
- **Tamper Evidence:** SHA-256 hash chain per record (similar to blockchain) stored in `audit_log_hashes` table
- **Access:** Read-only replica for auditors; direct writes only from `fintrac` module via `common/database.py::get_audit_session()`
- **Retention:** 7 years (exceeds FINTRAC 5-year requirement)

---

## 8. Testing Strategy

**Unit Tests (`tests/unit/test_fintrac.py`):**
- Mock encryption service, FINTRAC API adapter
- Test risk scoring with boundary values
- Test structuring detection algorithm with synthetic transaction streams

**Integration Tests (`tests/integration/test_fintrac_integration.py`):**
- Full flow: verification → report → submission (using FINTRAC sandbox API)
- Database constraints: immutable records, foreign key integrity
- Performance: query times with 10M+ records (use `pytest-benchmark`)

**Markers:**
- `@pytest.mark.unit` for logic tests
- `@pytest.mark.integration` for API and database tests
- `@pytest.mark.slow` for PEP registry update tasks

---

## 9. Deployment Considerations

**Infrastructure:**
- `celery-worker` pod for async tasks (PEP updates, structuring detection)
- Separate `fintrac-audit-db` PostgreSQL instance in dedicated VPC
- Vault policy for FINTRAC client certificate rotation

**Monitoring:**
- Prometheus metrics:
  - `fintrac_reports_pending_submission_total`
  - `fintrac_structuring_alerts_total`
  - `fintrac_api_submission_latency_seconds`
- AlertManager: Page compliance team if pending reports > 10 or submission fails > 5 times

**Scalability:**
- Partition `fintrac_reports` by `report_date` (monthly partitions)
- Use `pg_cron` to maintain indexes on partitioned tables
- Read replica for `GET /risk-assessment` queries

---

**WARNING:** This design assumes the existence of `clients`, `applications`, and `users` modules. If these modules lack required fields (e.g., `name_hash`, `dob_hash` for PEP matching), additional migrations will be needed.