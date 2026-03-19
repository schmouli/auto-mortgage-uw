# FINTRAC Compliance
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# FINTRAC Compliance Module Design

**File:** `docs/design/fintrac-compliance.md`  
**Module:** `fintrac`  
**Scope:** Identity verification, transaction reporting, risk assessment, and regulatory audit trail for Canadian mortgage underwriting.

---

## 1. Endpoints

### 1.1 `POST /api/v1/fintrac/applications/{application_id}/verify-identity`
**Purpose:** Submit identity verification for a client on a mortgage application.

**Path Parameters:**
- `application_id` (UUID, required) – Mortgage application identifier.

**Request Body (Pydantic):**
```python
{
  "client_id": UUID,                           # Target client on the application
  "verification_method": Enum["in_person", "credit_file", "dual_process"],
  "id_type": str,                              # e.g., "passport", "driver_license"
  "id_number": str,                            # Plain‑text; encrypted at rest (AES‑256)
  "id_expiry_date": date,                      # ISO 8601 date
  "id_issuing_province": str,                  # 2‑letter province code (e.g., "ON")
  "is_pep": bool = False,                      # Politically Exposed Person
  "is_hio": bool = False,                      # Head of International Organization
  "risk_level": Optional[Literal["low", "medium", "high"]]  # Auto‑computed if omitted
}
```

**Response (201 Created):**
```python
{
  "verification_id": UUID,
  "application_id": UUID,
  "client_id": UUID,
  "verification_method": str,
  "id_type": str,
  "id_expiry_date": date,
  "id_issuing_province": str,
  "verified_by": UUID,                         # JWT user sub
  "verified_at": datetime,
  "is_pep": bool,
  "is_hio": bool,
  "risk_level": str,
  "created_at": datetime
}
```

**Error Responses:**
| HTTP | Error Code | Scenario |
|------|------------|----------|
| 404 | `FINTRAC_001` | Application or client not found |
| 422 | `FINTRAC_003` | `id_number` missing / malformed province code / expired ID |
| 409 | `FINTRAC_006` | Verification already exists for this client on the application |
| 401 | – | Missing or invalid JWT |

**Auth:** Authenticated user with `underwriter` role.

---

### 1.2 `GET /api/v1/fintrac/applications/{application_id}/verification`
**Purpose:** Retrieve verification status for all clients on an application.

**Path Parameters:**
- `application_id` (UUID, required)

**Query Parameters:**
- `include_deleted` (bool, default `false`) – If `true`, includes soft‑deleted records (admin only).

**Response (200 OK):**
```python
{
  "application_id": UUID,
  "verifications": [
    {
      "verification_id": UUID,
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
      "created_at": datetime,
      "deleted_at": Optional[datetime]
    }
  ]
}
```
*Note:* `id_number` is **never** returned; a masked hash may be provided for correlation.

**Error Responses:**
| HTTP | Error Code | Scenario |
|------|------------|----------|
| 404 | `FINTRAC_001` | Application not found |
| 401 | – | Missing JWT |

**Auth:** Authenticated user (underwriter, auditor).

---

### 1.3 `POST /api/v1/fintrac/applications/{application_id}/report-transaction`
**Purpose:** File a FINTRAC report (large cash, suspicious, terrorist property).

**Path Parameters:**
- `application_id` (UUID, required)

**Request Body (Pydantic):**
```python
{
  "report_type": Enum["large_cash_transaction", "suspicious_transaction", "terrorist_property"],
  "amount": Decimal,                           # Must be > 0, ≤ 999,999,999.99
  "currency": str = "CAD",                     # ISO 4217 code
  "report_date": Optional[datetime]            # Defaults to now
}
```

**Response (201 Created):**
```python
{
  "report_id": UUID,
  "application_id": UUID,
  "report_type": str,
  "amount": Decimal,
  "currency": str,
  "report_date": datetime,
  "submitted_to_fintrac_at": Optional[datetime],
  "fintrac_reference_number": Optional[str],
  "created_by": UUID,
  "created_at": datetime
}
```

**Error Responses:**
| HTTP | Error Code | Scenario |
|------|------------|----------|
| 404 | `FINTRAC_001` | Application not found |
| 422 | `FINTRAC_003` | `amount` ≤ 0, malformed currency, or report type mismatch |
| 422 | `FINTRAC_007` | Amount exceeds system limit |
| 409 | `FINTRAC_004` | Report already submitted for this transaction ID (idempotency conflict) |
| 401 | – | Missing JWT |

**Auth:** Authenticated user with `underwriter` role.

---

### 1.4 `GET /api/v1/fintrac/applications/{application_id}/reports`
**Purpose:** List all FINTRAC reports filed for an application.

**Path Parameters:**
- `application_id` (UUID, required)

**Query Parameters:**
- `report_type` (Optional[Enum]) – Filter by type.
- `submitted` (Optional[bool]) – Filter by submission status.

**Response (200 OK):**
```python
{
  "application_id": UUID,
  "reports": [
    {
      "report_id": UUID,
      "report_type": str,
      "amount": Decimal,
      "currency": str,
      "report_date": datetime,
      "submitted_to_fintrac_at": Optional[datetime],
      "fintrac_reference_number": Optional[str],
      "created_by": UUID,
      "created_at": datetime
    }
  ]
}
```

**Error Responses:**
| HTTP | Error Code | Scenario |
|------|------------|----------|
| 404 | `FINTRAC_001` | Application not found |
| 401 | – | Missing JWT |

**Auth:** Authenticated user (underwriter, auditor).

---

### 1.5 `GET /api/v1/fintrac/risk-assessment/{client_id}`
**Purpose:** Retrieve consolidated risk assessment for a client across all applications.

**Path Parameters:**
- `client_id` (UUID, required)

**Response (200 OK):**
```python
{
  "client_id": UUID,
  "overall_risk_level": Literal["low", "medium", "high"],
  "factors": [
    {
      "source": "verification" | "report" | "pep_hio_list",
      "detail": str,
      "score_contribution": int
    }
  ],
  "verifications": [UUID],   # List of verification IDs
  "reports": [UUID]          # List of report IDs
}
```

**Error Responses:**
| HTTP | Error Code | Scenario |
|------|------------|----------|
| 404 | `FINTRAC_001` | Client not found |
| 401 | – | Missing JWT |

**Auth:** Authenticated user (underwriter, compliance officer).

---

## 2. Models & Database

### 2.1 `fintrac_verifications`
**Table Name:** `fintrac_verifications`

| Column | Type | Constraints | Index | Encrypted |
|--------|------|-------------|-------|-----------|
| `id` | UUID | PK, default `gen_random_uuid()` | – | – |
| `application_id` | UUID | FK → `mortgage_applications.id`, NOT NULL | Composite `(application_id, client_id)` | – |
| `client_id` | UUID | FK → `clients.id`, NOT NULL | Composite `(application_id, client_id)` | – |
| `verification_method` | VARCHAR(20) | Check `IN ('in_person','credit_file','dual_process')` | – | – |
| `id_type` | VARCHAR(50) | NOT NULL | – | – |
| `id_number_encrypted` | BYTEA | NOT NULL | – | **Yes (AES‑256)** |
| `id_expiry_date` | DATE | NOT NULL | – | – |
| `id_issuing_province` | VARCHAR(2) | Check `LENGTH=2` | – | – |
| `verified_by` | UUID | FK → `users.id`, NOT NULL | `idx_verified_by` | – |
| `verified_at` | TIMESTAMPTZ | NOT NULL, default `now()` | – | – |
| `is_pep` | BOOLEAN | NOT NULL, default `false` | `idx_is_pep` | – |
| `is_hio` | BOOLEAN | NOT NULL, default `false` | `idx_is_hio` | – |
| `risk_level` | VARCHAR(10) | Check `IN ('low','medium','high')` | `idx_risk_level` | – |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` | – | – |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()`, on update `now()` | – | – |
| `deleted_at` | TIMESTAMPTZ | Soft‑delete marker | `idx_deleted_at` | – |

**Relationships:**
- Many‑to‑One: `application` ← `mortgage_applications`
- Many‑to‑One: `client` ← `clients`
- Many‑to‑One: `verifier` ← `users`

**Indexes:**
- `idx_finv_app_client` ON `(application_id, client_id)` (unique together for idempotency guard).
- `idx_finv_risk` ON `(risk_level, is_pep, is_hio)` for compliance dashboards.

---

### 2.2 `fintrac_reports`
**Table Name:** `fintrac_reports`

| Column | Type | Constraints | Index | Encrypted |
|--------|------|-------------|-------|-----------|
| `id` | UUID | PK, default `gen_random_uuid()` | – | – |
| `application_id` | UUID | FK → `mortgage_applications.id`, NOT NULL | `idx_application_id` | – |
| `report_type` | VARCHAR(30) | Check `IN ('large_cash_transaction','suspicious_transaction','terrorist_property')` | `idx_report_type` | – |
| `amount` | DECIMAL(12,2) | NOT NULL, > 0 | `idx_amount` | – |
| `currency` | VARCHAR(3) | NOT NULL, default 'CAD' | – | – |
| `report_date` | TIMESTAMPTZ | NOT NULL, default `now()` | `idx_report_date` | – |
| `submitted_to_fintrac_at` | TIMESTAMPTZ | NULL (set after successful API submission) | `idx_submitted_at` | – |
| `fintrac_reference_number` | VARCHAR(100) | NULL, unique per submission | `idx_fintrac_ref` (unique) | – |
| `created_by` | UUID | FK → `users.id`, NOT NULL | `idx_created_by` | – |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` | – | – |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()`, on update `now()` | – | – |
| `deleted_at` | TIMESTAMPTZ | Soft‑delete marker | `idx_deleted_at` | – |

**Relationships:**
- Many‑to‑One: `application` ← `mortgage_applications`
- Many‑to‑One: `creator` ← `users`

**Indexes:**
- Composite `(application_id, report_type)` for quick listing.
- `idx_fintrac_ref` must be unique to avoid duplicate submissions.

---

## 3. Business Logic

### 3.1 Identity Verification Workflow
1. **Input Validation** – Verify that `application_id` and `client_id` exist and are linked. Ensure `id_expiry_date` is in the future. Validate province code against Canadian list.
2. **Encryption** – `id_number` is encrypted via `common.security.encrypt_pii()` before storage. The plaintext **never** touches the database or logs.
3. **Risk Score Calculation** (if not provided):
   - Base = 0.
   - Method: `in_person` = 0, `credit_file` = 10, `dual_process` = 5.
   - Province: QC/ON = 0; AB/BC = 5; others = 10.
   - PEP = +30; HIO = +20.
   - Thresholds: 0‑20 → `low`, 21‑40 → `medium`, 41+ → `high`.
4. **Store Record** – Insert into `fintrac_verifications` with `verified_by` = JWT `sub`.
5. **Audit Log** – Emit structured log: `{"event": "identity_verified", "application_id": "...", "client_id": "...", "risk_level": "...", "correlation_id": "..."}`.
6. **Enhanced Due Diligence Flag** – If `risk_level = 'high'` OR `is_pep = true` OR `is_hio = true`, raise a task for compliance officer review (via outbox pattern or task queue; implementation TBD).

### 3.2 Transaction Reporting Rules
- **Large Cash Transaction** – If `amount > 10,000` **and** `currency = CAD`, automatically require `report_type = 'large_cash_transaction'`. The endpoint rejects submissions with `amount > 10,000` and mismatched type.
- **Structuring Detection** – A scheduled Celery beat task (hourly) queries `fintrac_reports` for cash transactions `< 10,000` grouped by `client_id` and `DATE_TRUNC('hour', report_date)`. If ≥ 3 transactions within 24h or sum ≥ 10,000, the system auto‑creates a `suspicious_transaction` report with `amount = sum` and logs a `structuring_detected` event.
- **FINTRAC Submission** – On creation of a report, an async background worker (`FintracSubmissionService`) attempts to POST to FINTRAC’s REST API (mTLS auth). Success updates `submitted_to_fintrac_at` and `fintrac_reference_number`. Failure triggers exponential backoff (max 5 retries) and an alert to the compliance dashboard.

### 3.3 Risk Assessment Aggregation
- Combines all verifications and reports for a client.
- Factors include:
  - Highest `risk_level` from any verification.
  - Presence of PEP/HIO flags.
  - Count of `suspicious_transaction` reports.
  - Matches against external PEP/HIO list (see §5.1).
- Returns an overall `risk_level` = `max(low, medium, high)` and a human‑readable `factors` array for audit.

### 3.4 Record Retention & Soft‑Delete
- **Immutable Writes** – `UPDATE` operations on `fintrac_reports` are prohibited at the application layer (raised as `FintracBusinessRuleError`). Only `deleted_at` may be set.
- **Soft‑Delete** – All queries filter `WHERE deleted_at IS NULL`. Admins may view deleted records via `include_deleted` flag.
- **5‑Year Retention** – A monthly cron job archives records older than 5 years to a separate historical schema (`fintrac_archive_YYYY`) and sets `deleted_at` on the source row. Archival logs include `record_id` and `archive_date`.

---

## 4. Migrations

### Alembic Revision: `create_fintrac_tables`
```yaml
revision: 'xxxxx'
down_revision: 'previous'

operations:
  - create_table:
      name: fintrac_verifications
      columns:
        - { name: id, type: UUID, nullable: false, primary_key: true, default: gen_random_uuid() }
        - { name: application_id, type: UUID, nullable: false, foreign_key: { table: mortgage_applications, column: id } }
        - { name: client_id, type: UUID, nullable: false, foreign_key: { table: clients, column: id } }
        - { name: verification_method, type: VARCHAR(20), nullable: false }
        - { name: id_type, type: VARCHAR(50), nullable: false }
        - { name: id_number_encrypted, type: BYTEA, nullable: false }
        - { name: id_expiry_date, type: DATE, nullable: false }
        - { name: id_issuing_province, type: VARCHAR(2), nullable: false }
        - { name: verified_by, type: UUID, nullable: false, foreign_key: { table: users, column: id } }
        - { name: verified_at, type: TIMESTAMPTZ, nullable: false, default: now() }
        - { name: is_pep, type: BOOLEAN, nullable: false, default: false }
        - { name: is_hio, type: BOOLEAN, nullable: false, default: false }
        - { name: risk_level, type: VARCHAR(10), nullable: false }
        - { name: created_at, type: TIMESTAMPTZ, nullable: false, default: now() }
        - { name: updated_at, type: TIMESTAMPTZ, nullable: false, default: now(), onupdate: now() }
        - { name: deleted_at, type: TIMESTAMPTZ, nullable: true }
      indexes:
        - { name: idx_finv_app_client, columns: [application_id, client_id], unique: true }
        - { name: idx_finv_risk, columns: [risk_level, is_pep, is_hio] }
        - { name: idx_finv_verified_by, columns: [verified_by] }
        - { name: idx_finv_deleted_at, columns: [deleted_at] }

  - create_table:
      name: fintrac_reports
      columns:
        - { name: id, type: UUID, nullable: false, primary_key: true, default: gen_random_uuid() }
        - { name: application_id, type: UUID, nullable: false, foreign_key: { table: mortgage_applications, column: id } }
        - { name: report_type, type: VARCHAR(30), nullable: false }
        - { name: amount, type: DECIMAL(12,2), nullable: false }
        - { name: currency, type: VARCHAR(3), nullable: false, default: 'CAD' }
        - { name: report_date, type: TIMESTAMPTZ, nullable: false, default: now() }
        - { name: submitted_to_fintrac_at, type: TIMESTAMPTZ, nullable: true }
        - { name: fintrac_reference_number, type: VARCHAR(100), nullable: true }
        - { name: created_by, type: UUID, nullable: false, foreign_key: { table: users, column: id } }
        - { name: created_at, type: TIMESTAMPTZ, nullable: false, default: now() }
        - { name: updated_at, type: TIMESTAMPTZ, nullable: false, default: now(), onupdate: now() }
        - { name: deleted_at, type: TIMESTAMPTZ, nullable: true }
      indexes:
        - { name: idx_frep_app_type, columns: [application_id, report_type] }
        - { name: idx_frep_amount, columns: [amount] }
        - { name: idx_frep_submitted, columns: [submitted_to_fintrac_at] }
        - { name: idx_frep_fintrac_ref, columns: [fintrac_reference_number], unique: true }
        - { name: idx_frep_deleted_at, columns: [deleted_at] }

  - create_check_constraint:
      table: fintrac_verifications
      name: chk_finv_method
      condition: "verification_method IN ('in_person','credit_file','dual_process')"

  - create_check_constraint:
      table: fintrac_verifications
      name: chk_finv_risk_level
      condition: "risk_level IN ('low','medium','high')"

  - create_check_constraint:
      table: fintrac_reports
      name: chk_frep_type
      condition: "report_type IN ('large_cash_transaction','suspicious_transaction','terrorist_property')"

  - create_check_constraint:
      table: fintrac_reports
      name: chk_frep_amount_positive
      condition: "amount > 0"
```

**No data migration** is required for the initial release. Future revisions may back‑populate `risk_level` for historical verifications.

---

## 5. Security & Compliance

### 5.1 PIPEDA (Data Protection)
- **Encryption at Rest:** `id_number_encrypted` is encrypted with AES‑256‑GCM via `common.security.encrypt_pii()`. The encryption key is managed by `common.config.Settings.pii_encryption_key` (loaded from vault, never hardcoded).
- **Data Minimization:** Only `id_number` and `id_expiry_date` are collected; no other PII (e.g., full name, address) is stored in this module.
- **No Logging:** `id_number` plaintext is **never** logged. Logs include only `verification_id` and `client_id` for correlation.
- **Access Control:** Endpoints require JWT authentication; users can only view data for their authorized institution (row‑level security enforced in service layer).

### 5.2 FINTRAC (Reporting & Retention)
- **Immutable Audit Trail:** `fintrac_reports` rows are **append‑only**. Application code rejects `UPDATE` attempts with `FintracBusinessRuleError`. `deleted_at` is the only mutable column.
- **Large Cash Threshold:** Hardcoded at CAD 10,000; configurable via `common.config.FINTRAC_LARGE_CASH_THRESHOLD` for tuning.
- **Structuring Detection:** Background job runs hourly; flags are stored as new `suspicious_transaction` reports. The job logs `structuring_detected` events with `client_id` and `transaction_count`.
- **5‑Year Retention:** Soft‑deleted records remain queryable for 5 years; after that, a monthly cron archives them to `fintrac_archive_YYYY` schema and marks source rows as deleted. Archive location is logged for audit.
- **FINTRAC API Integration:**
  - **Auth:** mTLS using client certificate from vault.
  - **Endpoint:** `https://api.fintrac-canafe.gc.ca/v1/reports` (sandbox URL configurable).
  - **Payload:** JSON matching FINTRAC’s `ReportSubmission` schema (contains report ID, type, amount, currency, timestamp).
  - **Response:** 200 OK with `referenceNumber`; 4xx/5xx trigger retry logic.
  - **Idempotency:** `fintrac_reference_number` uniqueness prevents duplicate submissions.

### 5.3 PEP/HIO List Integration (Future)
- **Source:** Subscribe to official PEP/HIO data feed (e.g., OSFI‑sanctioned list).
- **Sync Job:** Daily batch downloads CSV/JSON, parses into `pep_hio_list` table (columns: `name`, `dob`, `country`, `list_date`).
- **Verification Check:** During identity verification, the service queries `pep_hio_list` by normalized name/DOB hash; if match, sets `is_pep`/`is_hio` and logs `pep_hio_match`.

### 5.4 OSFI B‑20 (Indirect)
- This module does **not** compute GDS/TDS, but all `amount` fields must use `Decimal` to avoid precision loss, satisfying the “no float” rule.

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `FintracVerificationNotFoundError` | 404 | `FINTRAC_001` | "Verification for application {id} not found" | `GET` on non‑existent verification |
| `FintracReportNotFoundError` | 404 | `FINTRAC_002` | "Report {id} not found" | `GET` on non‑existent report |
| `FintracValidationError` | 422 | `FINTRAC_003` | "{field}: {reason}" | Missing `id_number`, invalid province, `amount ≤ 0` |
| `FintracBusinessRuleError` | 409 | `FINTRAC_004` | "Business rule violated: {detail}" | Attempt to update a report, duplicate verification |
| `FintracRiskAssessmentError` | 422 | `FINTRAC_005` | "Risk assessment failed: {detail}" | PEP/HIO list unavailable |
| `FintracDuplicateVerificationError` | 409 | `FINTRAC_006` | "Verification already exists for client {client_id}" | Double `POST` for same client/app |
| `FintracTransactionThresholdError` | 422 | `FINTRAC_007` | "Amount must be >0 and ≤ 999,999,999.99" | `amount` out of bounds |

**Error Response Format (consistent across endpoints):**
```json
{
  "detail": "Verification for application 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "FINTRAC_001",
  "timestamp": "2025-06-28T14:30:00Z",
  "correlation_id": "req-abc123"
}
```

---

## 7. Missing Details & Future Enhancements

| Topic | Current Design | Recommendation |
|-------|----------------|----------------|
| **PEP/HIO List Integration** | Manual flagging via request body | Implement daily sync job + `pep_hio_list` table; auto‑populate `is_pep`/`is_hio`. |
| **Risk Scoring Weights** | Static point system | Make weights configurable via `common.config` to allow tuning without code deploy. |
| **FINTRAC API Details** | Stub background worker | Define OpenAPI spec for FINTRAC client; add circuit‑breaker and Prometheus metrics for submission latency. |
| **Transaction Monitoring Tuning** | Fixed 24‑hour window | Expose window size (`STRUCTURING_TIME_WINDOW_HOURS`) and transaction count threshold (`STRUCTURING_COUNT_THRESHOLD`) in config. |
| **Audit Trail for FINTRAC Actions** | Structured logs | Consider append‑only `fintrac_audit_log` table for non‑repudiation (stores `user_id`, `action`, `record_id`, `timestamp`). |
| **Multi‑Tenancy** | Implicit in user auth | Add `institution_id` column to both tables and enforce row‑level security in SQLAlchemy middleware. |

---

**Compliance Summary:** This design satisfies FINTRAC’s mandatory verification, reporting, and 5‑year retention requirements; respects PIPEDA encryption and minimization; and aligns with the project’s async, Decimal‑only, and soft‑delete conventions.