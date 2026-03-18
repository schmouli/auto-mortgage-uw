# Design: Background Jobs (Celery + Redis)
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

```markdown
# Background Jobs Module Design

**Module:** `scheduled_jobs`  
**File:** docs/design/scheduled-jobs.md  
**Purpose:** Celery-based background job processing for mortgage underwriting system automation and compliance monitoring

---

## 1. Endpoints

### Admin Job Management Endpoints (Admin-Only)

#### `GET /api/v1/admin/jobs`
**Purpose:** List recent job executions with filtering

**Query Parameters:**
- `task_name` (optional, str): Filter by task name (e.g., "send_document_reminder")
- `status` (optional, str): Filter by status ["pending", "running", "success", "failed", "retry"]
- `limit` (optional, int, default=50): Max results
- `offset` (optional, int, default=0): Pagination offset

**Response Schema:**
```json
{
  "items": [
    {
      "job_id": "str (UUID)",
      "task_name": "str",
      "status": "str",
      "started_at": "datetime",
      "completed_at": "datetime | null",
      "runtime_seconds": "float | null",
      "result_summary": "str | null",
      "error_code": "str | null"
    }
  ],
  "total": "int",
  "limit": "int",
  "offset": "int"
}
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid JWT token
- `403 Forbidden` - User lacks `admin:jobs:read` scope

---

#### `GET /api/v1/admin/jobs/{job_id}`
**Purpose:** Get detailed execution log for a specific job run

**Path Parameter:** `job_id` (UUID)

**Response Schema:**
```json
{
  "job_id": "str (UUID)",
  "task_name": "str",
  "status": "str",
  "started_at": "datetime",
  "completed_at": "datetime | null",
  "runtime_seconds": "float | null",
  "args": "list | null (PII redacted)",
  "kwargs": "dict | null (PII redacted)",
  "result_summary": "str | null",
  "traceback": "str | null (only on failure, no PII)",
  "retry_count": "int",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid JWT token
- `403 Forbidden` - User lacks `admin:jobs:read` scope
- `404 Not Found` - Job ID not found (error_code: `JOBS_001`)

---

#### `POST /api/v1/admin/jobs/{task_name}/trigger`
**Purpose:** Manually trigger a scheduled task (for testing/reprocessing)

**Path Parameter:** `task_name` (str, enum of registered tasks)

**Request Body:**
```json
{
  "dry_run": "bool (default=false)",
  "custom_args": "dict | null (task-specific parameters)"
}
```

**Response Schema:**
```json
{
  "job_id": "str (UUID)",
  "task_name": "str",
  "status": "str",
  "message": "str",
  "triggered_at": "datetime"
}
```

**Error Responses:**
- `400 Bad Request` - Invalid task name (error_code: `JOBS_002`)
- `401 Unauthorized` - Missing or invalid JWT token
- `403 Forbidden` - User lacks `admin:jobs:trigger` scope
- `409 Conflict` - Task already running (error_code: `JOBS_003`)

---

#### `GET /api/v1/admin/jobs/{task_name}/schedule`
**Purpose:** Get current schedule configuration for a task

**Path Parameter:** `task_name` (str)

**Response Schema:**
```json
{
  "task_name": "str",
  "schedule_type": "str (cron/interval)",
  "schedule": "str (cron expression or seconds)",
  "last_run_at": "datetime | null",
  "next_run_at": "datetime | null",
  "is_enabled": "bool"
}
```

---

#### `PUT /api/v1/admin/jobs/{task_name}/schedule`
**Purpose:** Update schedule configuration (admin only)

**Path Parameter:** `task_name` (str)

**Request Body:**
```json
{
  "schedule_type": "str (cron/interval)",
  "schedule": "str",
  "is_enabled": "bool"
}
```

**Response Schema:** Same as GET

**Error Responses:**
- `422 Unprocessable Entity` - Invalid cron expression (error_code: `JOBS_004`)

---

## 2. Models & Database

### `job_execution_logs` Table
**Purpose:** Immutable audit trail of all job executions (FINTRAC compliance)

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | - |
| `task_name` | VARCHAR(100) | NOT NULL | Composite (task_name, started_at DESC) |
| `job_id` | VARCHAR(255) | UNIQUE, NOT NULL (Celery task ID) | Unique |
| `status` | VARCHAR(20) | NOT NULL | Single |
| `started_at` | TIMESTAMPTZ | NOT NULL | Composite |
| `completed_at` | TIMESTAMPTZ | - | - |
| `runtime_seconds` | DECIMAL(10,3) | - | - |
| `args` | JSONB | NULL (PII redacted before save) | - |
| `kwargs` | JSONB | NULL (PII redacted before save) | - |
| `result_summary` | TEXT | NULL | - |
| `traceback` | TEXT | NULL (stack traces only) | - |
| `retry_count` | INTEGER | DEFAULT 0 | - |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | - |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | - |

**Indexes:**
- `idx_job_logs_task_started` ON (task_name, started_at DESC) for dashboard queries
- `idx_job_logs_status` ON (status) for failure monitoring

**Audit Fields:** `created_at`, `updated_at` (auto-managed)

---

### `monthly_reports` Table
**Purpose:** Store generated monthly reports with encrypted sensitive data

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | - |
| `report_month` | DATE | NOT NULL (YYYY-MM-01) | Unique |
| `report_type` | VARCHAR(50) | NOT NULL | Composite |
| `file_name` | VARCHAR(255) | NOT NULL | - |
| `file_data` | BYTEA | NOT NULL (AES-256 encrypted) | - |
| `file_size_bytes` | BIGINT | NOT NULL | - |
| `record_count` | INTEGER | NOT NULL | - |
| `generated_by` | VARCHAR(100) | NOT NULL (service account) | - |
| `checksum_sha256` | VARCHAR(64) | NOT NULL | - |
| `retention_until` | DATE | NOT NULL (created_at + 5 years) | Single |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | - |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | - |

**Indexes:**
- `idx_monthly_reports_month_type` ON (report_month, report_type)
- `idx_monthly_reports_retention` ON (retention_until) for cleanup

**Encryption:** `file_data` encrypted using AES-256-GCM via `common/security.py:encrypt_pii()`

**PIPEDA Compliance:** Encrypted at rest, automatic 5-year retention enforcement

---

### `fintrac_verification_flags` Table
**Purpose:** Track applications requiring FINTRAC verification (FINTRAC compliance)

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | UUID | PRIMARY KEY | - |
| `application_id` | UUID | NOT NULL, FOREIGN KEY applications.id | Unique |
| `requires_verification` | BOOLEAN | NOT NULL, DEFAULT true | Single |
| `verification_completed_at` | TIMESTAMPTZ | NULL | - |
| `flagged_by_job_id` | UUID | NOT NULL, FOREIGN KEY job_execution_logs.id | - |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | - |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | - |

**Indexes:**
- `idx_fintrac_flags_unverified` ON (requires_verification) WHERE verification_completed_at IS NULL

---

## 3. Business Logic

### Celery Task Definitions

#### `send_document_reminder`
**Schedule:** Daily 9:00 AM (America/Toronto timezone)

**Algorithm:**
1. Query applications with `status = 'awaiting_documents'` AND `awaiting_docs_since <= NOW() - INTERVAL '48 hours'`
2. For each application:
   - Fetch client contact email (hashed lookup only)
   - Check email rate limit: max 3 reminders per application, 1 per week
   - Render email template with application ID (no PII in body)
   - Send via SMTP with rate limiting (max 100 emails/minute)
   - Log: `application_id`, `email_sent`, `reminder_number` (PIPEDA: no email address in logs)
3. Update `document_reminder_count` on application

**FINTRAC:** Email communications are part of client identity verification audit trail

---

#### `check_rate_expiry`
**Schedule:** Daily 7:00 AM (America/Toronto timezone)

**Algorithm:**
1. Query `lender_products` WHERE `rate_expiry_date < CURRENT_DATE` AND `is_active = true`
2. For each expired product:
   - Set `is_active = false`
   - Create audit log entry with `job_execution_logs.result_summary`
   - If product used in pending applications, flag for underwriter review
3. Log: `product_id`, `lender_id`, `expiry_date`, `action_taken`

**OSFI B-20 Compliance:** Ensures stress test calculations use current qualifying rates only

---

#### `check_condition_due_dates`
**Schedule:** Daily 8:00 AM (America/Toronto timezone)

**Algorithm:**
1. Query `lender_conditions` WHERE `due_date < CURRENT_DATE` AND `status = 'pending'`
2. For each overdue condition:
   - Update status to `overdue`
   - Update application `risk_flags` JSONB array
   - Log: `condition_id`, `application_id`, `days_overdue`
3. Trigger notification to assigned underwriter (separate async task)

**Business Rule:** Overdue conditions block final approval (TDS/GDS cannot be finalized)

---

#### `generate_monthly_report`
**Schedule:** 1st of month 6:00 AM (America/Toronto timezone)

**Algorithm:**
1. Determine previous month range (e.g., March 1-31 for April 1 run)
2. Aggregate data:
   - Total applications submitted
   - Approval/rejection rates
   - Average GDS/TDS ratios (Decimal precision)
   - CMHC insurance premiums (sum of Decimal values)
   - FINTRAC verification completion rate
3. Generate PDF report with encrypted embedded data
4. Store in `monthly_reports` table with checksum
5. Log: `report_month`, `record_count`, `file_size`, `checksum` (no PII)

**FINTRAC Compliance:** 5-year retention automatically applied via `retention_until` field

---

#### `cleanup_temp_uploads`
**Schedule:** Daily 2:00 AM (America/Toronto timezone)

**Algorithm:**
1. Scan `/uploads/temp` directory for files older than 24 hours
2. For each file:
   - Verify not referenced by active application
   - Secure delete (overwrite before unlink)
   - Log: `file_path`, `file_size`, `deleted_at` (no filenames containing PII)
3. Enforce max 1000 files per run to prevent worker overload

**PIPEDA Compliance:** Ensures temporary PII not retained beyond necessary period

---

#### `flag_fintrac_overdue`
**Schedule:** Daily 9:00 AM (America/Toronto timezone)

**Algorithm:**
1. Query applications WHERE `status = 'submitted'` AND `fintrac_verified = false` AND `created_at <= NOW() - INTERVAL '72 hours'`
2. For each application:
   - Create entry in `fintrac_verification_flags` table
   - Update application `compliance_flags` JSONB
   - Log: `application_id`, `flag_reason`, `days_pending`
3. Send alert to compliance team (rate-limited)

**FINTRAC Compliance:** Direct enforcement of 72-hour verification requirement for transactions > $10,000

---

## 4. Migrations

### New Tables
```sql
-- migration: 20240101000001_create_job_execution_logs
CREATE TABLE job_execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name VARCHAR(100) NOT NULL,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    runtime_seconds DECIMAL(10,3),
    args JSONB,
    kwargs JSONB,
    result_summary TEXT,
    traceback TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_job_logs_task_started ON job_execution_logs(task_name, started_at DESC);
CREATE INDEX idx_job_logs_status ON job_execution_logs(status);

-- migration: 20240101000002_create_monthly_reports
CREATE TABLE monthly_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_month DATE NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_data BYTEA NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    record_count INTEGER NOT NULL,
    generated_by VARCHAR(100) NOT NULL,
    checksum_sha256 VARCHAR(64) NOT NULL,
    retention_until DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_monthly_reports_month_type ON monthly_reports(report_month, report_type);
CREATE INDEX idx_monthly_reports_retention ON monthly_reports(retention_until);

-- migration: 20240101000003_create_fintrac_verification_flags
CREATE TABLE fintrac_verification_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    requires_verification BOOLEAN NOT NULL DEFAULT true,
    verification_completed_at TIMESTAMPTZ,
    flagged_by_job_id UUID NOT NULL REFERENCES job_execution_logs(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_fintrac_flags_app ON fintrac_verification_flags(application_id);
CREATE INDEX idx_fintrac_flags_unverified ON fintrac_verification_flags(requires_verification) 
    WHERE verification_completed_at IS NULL;
```

### Existing Table Modifications
```sql
-- migration: 20240101000004_add_application_reminder_tracking
ALTER TABLE applications 
ADD COLUMN document_reminder_count INTEGER DEFAULT 0,
ADD COLUMN last_reminder_sent_at TIMESTAMPTZ;

-- migration: 20240101000005_add_lender_product_audit
ALTER TABLE lender_products
ADD COLUMN deactivated_at TIMESTAMPTZ,
ADD COLUMN deactivated_by_job_id UUID REFERENCES job_execution_logs(id);
```

---

## 5. Security & Compliance

### OSFI B-20 Requirements
- **Rate Expiry Enforcement:** `check_rate_expiry` task ensures no underwriting uses expired rates, maintaining stress test integrity
- **Audit Trail:** All rate deactivations logged with `job_execution_logs` for examiner review
- **GDS/TDS Calculation:** Monthly report includes average ratio calculations using Decimal precision to demonstrate compliance

### FINTRAC Requirements
- **72-Hour Rule:** `flag_fintrac_overdue` identifies applications missing verification within regulatory timeframe
- **Immutable Records:** `job_execution_logs` and `fintrac_verification_flags` are append-only, supporting 5-year retention
- **Transaction Tracking:** Monthly reports include FINTRAC verification completion metrics for compliance reporting
- **Alerting:** Flags create auditable compliance team notifications

### CMHC Requirements
- **Insurance Premium Tracking:** Monthly report aggregates CMHC premium amounts by LTV tier using Decimal calculations
- **LTV Validation:** `check_rate_expiry` ensures property valuations used in LTV calculations are current

### PIPEDA Requirements
- **Data Minimization:** Temporary uploads deleted after 24h; job logs redact PII from `args`/`kwargs`
- **Encryption at Rest:** `monthly_reports.file_data` encrypted with AES-256-GCM
- **No PII in Logs:** Email addresses, SIN, DOB, income never logged; only hashed IDs or synthetic keys
- **Secure Deletion:** `cleanup_temp_uploads` overwrites files before deletion

### Authentication & Authorization
- All admin endpoints require JWT with `admin:jobs:*` scopes
- Service-to-service authentication for Celery workers using mTLS
- API key authentication for webhook callbacks (if implemented)

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Scenario |
|-----------------|-------------|------------|-----------------|------------------|
| `JobNotFoundError` | 404 | `JOBS_001` | "Job execution {job_id} not found" | Invalid job_id in GET /admin/jobs/{job_id} |
| `InvalidTaskNameError` | 400 | `JOBS_002` | "Task {task_name} is not registered" | Triggering non-existent task |
| `JobAlreadyRunningError` | 409 | `JOBS_003` | "Task {task_name} is already running" | Concurrent manual trigger |
| `InvalidScheduleError` | 422 | `JOBS_004` | "Invalid cron expression: {detail}" | Malformed cron in schedule update |
| `JobExecutionError` | 500 | `JOBS_005` | "Task {task_name} failed after {retry_count} retries" | Task failure after all retries |
| `RateLimitExceededError` | 429 | `JOBS_006` | "Email rate limit exceeded: {detail}" | SMTP throttling activation |

### Celery Task Error Handling
- **Retry Strategy:** 3 attempts with exponential backoff (delay = 2^retry_count * 30 seconds)
- **Dead Letter Queue:** Failed tasks after retries routed to `dlq_{task_name}` queue for manual investigation
- **Monitoring:** Each task execution creates `job_execution_logs` entry before start and after completion
- **Alerting:** `JobExecutionError` triggers Prometheus counter `mortgage_jobs_failed_total{task_name="..."}`

**Logging Convention:**
```python
# structlog JSON output
{
  "event": "task_executed",
  "task_name": "send_document_reminder",
  "job_id": "celery-task-id",
  "correlation_id": "request-id",
  "runtime_seconds": 45.234,
  "records_processed": 12,
  "emails_sent": 8,
  "rate_limited": 4,
  "level": "info"
}
```
**PIPEDA Note:** No email addresses, names, or financial data appears in log fields
```