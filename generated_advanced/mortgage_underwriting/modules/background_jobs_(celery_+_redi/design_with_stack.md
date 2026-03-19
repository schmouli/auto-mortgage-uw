# Design: Background Jobs (Celery + Redis)
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# docs/design/background_jobs.md

**Module:** `jobs` – Background task scheduling & execution (Celery + Redis)  
**Feature slug:** `background_jobs`  
**Version:** 1.0  
**Last Updated:** 2025-07-09

---

## 1. Endpoints

| Method | Path | Auth | Request Body | Response Body | Status Codes | Error Codes |
|--------|------|------|--------------|---------------|--------------|-------------|
| `POST` | `/api/v1/jobs/{job_name}/run` | admin‑only | `JobExecutionRequest` (optional params) | `JobExecutionResponse` | `202 Accepted`, `404`, `409`, `422` | `JOB_001`, `JOB_002`, `JOB_003` |
| `GET`  | `/api/v1/jobs/{job_name}/status` | admin‑only | – | `ScheduledJobSchema` | `200`, `404` | `JOB_001` |
| `GET`  | `/api/v1/jobs/executions` | admin‑only | `JobExecutionFilterQuery` (query params) | `List[JobExecutionLogSchema]` | `200` | – |
| `PATCH`| `/api/v1/jobs/{job_name}` | admin‑only | `JobEnableRequest` (enabled: bool) | `ScheduledJobSchema` | `200`, `404`, `422` | `JOB_001`, `JOB_003` |
| `GET`  | `/api/v1/jobs/scheduled` | admin‑only | – | `List[ScheduledJobSchema]` | `200` | – |

### Request/Response Schemas

#### `JobExecutionRequest`
```json
{
  "params": { "date_range": { "start": "2025-06-01", "end": "2025-06-30" } }
}
```
- `params` – optional JSON object passed to the Celery task (validated against a per‑task JSON schema).

#### `JobExecutionResponse`
```json
{
  "execution_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "job_name": "send_document_reminder",
  "status": "queued",
  "started_at": "2025-07-09T09:00:00Z"
}
```

#### `ScheduledJobSchema`
```json
{
  "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "name": "send_document_reminder",
  "schedule": "0 9 * * *",
  "last_run": "2025-07-08T09:00:05Z",
  "next_run": "2025-07-09T09:00:00Z",
  "enabled": true,
  "created_at": "2025-07-01T00:00:00Z",
  "updated_at": "2025-07-08T09:00:05Z"
}
```

#### `JobExecutionLogSchema`
```json
{
  "id": "b2c3d4e5-f6a7-8901-2345-67890abcdef1",
  "job_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "started_at": "2025-07-09T09:00:00Z",
  "finished_at": "2025-07-09T09:02:15Z",
  "status": "success",
  "result": { "emails_sent": 42 },
  "error_message": null,
  "created_at": "2025-07-09T09:00:00Z",
  "updated_at": "2025-07-09T09:02:15Z"
}
```

---

## 2. Models & Database

### 2.1 `ScheduledJob` (Table: `scheduled_jobs`)
| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `UUID` | `primary_key`, `default=gen_random_uuid()` | – |
| `name` | `String(64)` | `unique`, `nullable=False` | `idx_scheduled_job_name` |
| `schedule` | `String(128)` | `nullable=False` (cron format) | – |
| `last_run` | `DateTime(timezone=True)` | `nullable=True` | `idx_scheduled_job_last_run` |
| `next_run` | `DateTime(timezone=True)` | `nullable=True` | `idx_scheduled_job_next_run` |
| `enabled` | `Boolean` | `default=True` | `idx_scheduled_job_enabled` |
| `created_at` | `DateTime(timezone=True)` | `default=now()`, `nullable=False` | – |
| `updated_at` | `DateTime(timezone=True)` | `default=now()`, `onupdate=now()` | – |

**Relationships:** None (standalone configuration table).

### 2.2 `JobExecutionLog` (Table: `job_execution_logs`)
| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `UUID` | `primary_key`, `default=gen_random_uuid()` | – |
| `job_id` | `UUID` | `ForeignKey('scheduled_jobs.id')`, `nullable=False` | `idx_job_exec_log_job_id` |
| `started_at` | `DateTime(timezone=True)` | `nullable=False` | `idx_job_exec_log_started_at` |
| `finished_at` | `DateTime(timezone=True)` | `nullable=True` | – |
| `status` | `Enum('running','success','failed')` | `nullable=False` | `idx_job_exec_log_status` |
| `result` | `JSONB` | `nullable=True` (store task result) | – |
| `error_message` | `Text` | `nullable=True` (only on failure) | – |
| `created_at` | `DateTime(timezone=True)` | `default=now()`, `nullable=False` | – |
| `updated_at` | `DateTime(timezone=True)` | `default=now()`, `onupdate=now()` | – |

**Composite indexes:** `(job_id, started_at DESC)`, `(status, created_at)` for filtering.

### 2.3 `MonthlyReport` (Table: `monthly_reports`)
| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| `id` | `UUID` | `primary_key` | – |
| `report_month` | `Date` | `nullable=False`, `unique` | `idx_monthly_report_month` |
| `report_data` | `JSONB` | `nullable=False` (aggregated metrics) | – |
| `file_path` | `String(255)` | `nullable=True` (S3 / local path) | – |
| `created_at` | `DateTime(timezone=True)` | `default=now()` | – |
| `updated_at` | `DateTime(timezone=True)` | `default=now()`, `onupdate=now()` | – |

**Note:** All financial values stored inside `report_data` use `Decimal` (serialized as string in JSON).

---

## 3. Business Logic

### 3.1 Job Definitions (Celery tasks)

| Task Name | Schedule | Purpose | Logic Outline |
|-----------|----------|---------|---------------|
| `send_document_reminder` | `0 9 * * *` (9 AM daily) | Email clients with missing documents | 1. Query `applications` where `status = 'documents_pending'` and `last_reminder_sent < now() - interval '2 days'` <br>2. For each app, render Jinja2 email template (no SIN/DOB in body) <br>3. Send via `EmailService.send()` with rate limit = 100/min <br>4. Update `last_reminder_sent = now()` <br>5. Log `result: {emails_sent: N}` |
| `check_rate_expiry` | `0 7 * * *` (7 AM daily) | Flag expired lender rates | 1. Query `lender_products` where `rate_expiry_date < now()` and `status = 'active'` <br>2. Update status to `'expired'` <br>3. Insert audit log entries (`lender_product_audit`) <br>4. Log `result: {products_expired: N}` |
| `check_condition_due_dates` | `0 8 * * *` (8 AM daily) | Flag overdue lender conditions | 1. Query `lender_conditions` where `due_date < now()` and `status = 'pending'` <br>2. Update status to `'overdue'` <br>3. Insert audit logs (`condition_audit`) <br>4. Log `result: {conditions_flagged: N}` |
| `generate_monthly_report` | `0 6 1 * *` (1st 6 AM) | Generate & store monthly underwriting metrics | 1. Determine previous month range (e.g., 2025‑06‑01 to 2025‑06‑30) <br>2. Aggregate: total applications, approved count, declined count, avg GDS/TDS (using **OSFI B‑20 stress test** `qualifying_rate = max(contract_rate + 2%, 5.25%)`), avg LTV, CMHC‑insured count, etc. All calculations use `Decimal`. <br>3. Store JSON result in `monthly_reports.report_data` <br>4. Optionally write PDF to `file_path` (S3) <br>5. Log `result: {report_month: '2025-06', record_count: N}` |
| `cleanup_temp_uploads` | `0 2 * * *` (2 AM daily) | Delete temp files older than 24 h | 1. Scan `/uploads/temp` (or S3 prefix) for files with `mtime < now() - 24h` <br>2. Delete each file <br>3. Log `result: {files_deleted: N}` |
| `flag_fintrac_overdue` | `0 9 * * *` (9 AM daily) | Flag applications missing FINTRAC verification | 1. Query `applications` where `fintrac_verified = false` and `created_at < now() - interval '30 days'` <br>2. Update status to `'fintrac_overdue'` <br>3. Insert FINTRAC audit log (for 5‑yr retention) <br>4. Log `result: {applications_flagged: N}` |

### 3.2 Retry & DLQ Policy
| Failure Type | Retry Strategy | Dead‑Letter Queue |
|--------------|----------------|-------------------|
| **Transient** (DB deadlock, network glitch) | Exponential backoff: 3 attempts, base delay = 30 s, factor = 2, max delay = 10 min | Route to `dead_letter` queue after final failure. |
| **Permanent** (validation error, missing config) | No retry, log error immediately | Directly log to `JobExecutionLog.error_message`. |

### 3.3 Rate Limiting & Throttling
- **Email sending**: Celery task `rate_limit='100/m'` (100 emails per minute).  
- **API endpoints**: Standard `RateLimiter` middleware (e.g., 10 req/s per admin user).  

### 3.4 Observability
- **Metrics** (Prometheus):  
  - `job_execution_total{job_name, status}`  
  - `job_execution_duration_seconds{job_name}`  
  - `job_failures_total{job_name, error_type}`  
- **Logging**: `structlog` JSON, `correlation_id` propagated from FastAPI request or Celery task ID. **Never log SIN, DOB, income, or banking data**.  
- **Tracing**: OpenTelemetry spans for each job step (DB query, email send, file delete).  

---

## 4. Migrations

### New Alembic Revision: `create_job_scheduler_tables`

```yaml
revision: '20250709000001'
description: 'Add scheduled_jobs, job_execution_logs, monthly_reports tables'
```

#### DDL
```sql
CREATE TABLE scheduled_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(64) NOT NULL UNIQUE,
    schedule VARCHAR(128) NOT NULL,
    last_run TIMESTAMPTZ,
    next_run TIMESTAMPTZ,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_scheduled_job_name ON scheduled_jobs(name);
CREATE INDEX idx_scheduled_job_last_run ON scheduled_jobs(last_run);
CREATE INDEX idx_scheduled_job_next_run ON scheduled_jobs(next_run);
CREATE INDEX idx_scheduled_job_enabled ON scheduled_jobs(enabled);

CREATE TABLE job_execution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES scheduled_jobs(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status VARCHAR(16) NOT NULL CHECK (status IN ('running','success','failed')),
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_job_exec_log_job_id ON job_execution_logs(job_id);
CREATE INDEX idx_job_exec_log_started_at ON job_execution_logs(started_at DESC);
CREATE INDEX idx_job_exec_log_status ON job_execution_logs(status);
CREATE INDEX idx_job_exec_log_created_at ON job_execution_logs(created_at);
CREATE INDEX idx_job_exec_log_composite ON job_execution_logs(job_id, started_at DESC);

CREATE TABLE monthly_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_month DATE NOT NULL UNIQUE,
    report_data JSONB NOT NULL,
    file_path VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_monthly_report_month ON monthly_reports(report_month);
```

#### Seed Data (insert scheduled job definitions)
```sql
INSERT INTO scheduled_jobs (name, schedule, enabled) VALUES
('send_document_reminder', '0 9 * * *', TRUE),
('check_rate_expiry', '0 7 * * *', TRUE),
('check_condition_due_dates', '0 8 * * *', TRUE),
('generate_monthly_report', '0 6 1 * *', TRUE),
('cleanup_temp_uploads', '0 2 * * *', TRUE),
('flag_fintrac_overdue', '0 9 * * *', TRUE);
```

---

## 5. Security & Compliance

### 5.1 Authentication & Authorization
- All endpoints require a valid JWT with `admin` scope.  
- Role‑based access control (RBAC) enforced via `security.py:require_admin()`.

### 5.2 PIPEDA (Data Protection)
- **No PII in logs**: Filters strip SIN, DOB, income, banking data from task arguments and result JSON.  
- **Encryption at rest**: If any job needs to store SIN/DOB temporarily, use `encrypt_pii()` before writing to DB.  
- **Data minimization**: Jobs only fetch required fields (e.g., `SELECT id, email, status` rather than `*`).

### 5.3 FINTRAC (AML)
- `flag_fintrac_overdue` creates immutable audit records (`fintrac_audit` table) for every flagged application (5‑year retention).  
- Audit entry includes `application_id`, `reason_code`, `flagged_at`, `created_by` (system user).  
- No deletion or modification of audit rows (FINTRAC requirement).

### 5.4 OSFI B‑20 (Mortgage Stress Test)
- `generate_monthly_report` calculates GDS/TDS using the **qualifying rate** formula:  
  `qualifying_rate = max(contract_rate + Decimal('0.02'), Decimal('0.0525'))`.  
- All ratio results stored as `Decimal` (string in JSONB) to avoid precision loss.  
- Audit logs capture the exact rate used for each application in the monthly rollup.

### 5.5 CMHC Insurance
- `generate_monthly_report` includes LTV‑based insurance premium tiers (80.01‑85% → 2.80%, 85.01‑90% → 3.10%, 90.01‑95% → 4.00%).  
- Premium values stored as `Decimal` in `report_data`.

### 5.6 Network & Infrastructure
- Redis broker uses `redis://localhost:6379/0` (configurable via `common/config.py`).  
- Celery worker pool size set to `worker_concurrency = 4` (tunable via env var).  
- mTLS enabled for inter‑service communication (if workers span hosts).  

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | When Raised |
|-----------------|-------------|------------|-----------------|-------------|
| `JobNotFoundError` | `404` | `JOB_001` | "Job '{job_name}' not found" | `GET/POST/PATCH` on non‑existent job |
| `JobExecutionConflictError` | `409` | `JOB_002` | "Job '{job_name}' is already running" | Attempt to run a job whose latest status is `running` |
| `JobValidationError` | `422` | `JOB_003` | "Invalid params: {detail}" | `params` fails JSON schema validation |
| `JobExecutionError` | `500` | `JOB_004` | "Job execution failed: {detail}" | Unhandled exception in task (logged, not retried) |
| `JobScheduleUpdateError` | `409` | `JOB_005` | "Cannot disable mandatory job '{job_name}'" | Attempt to disable a FINTRAC‑mandated job |

**Error Response Format** (consistent across all endpoints):
```json
{
  "detail": "Job 'send_document_reminder' not found",
  "error_code": "JOB_001"
}
```

---

## 7. Monitoring & Alerting

| Metric | Threshold | Alert Destination |
|--------|-----------|-------------------|
| `job_failures_total` (rate) > 5 failures / 10 min | PagerDuty + Slack `#alerts‑jobs` |
| `job_execution_duration_seconds` (p99) > 300 s | Slack `#perf‑jobs` |
| `redis_connected_clients` < 2 (beat & worker) | PagerDuty |
| `disk_usage_percent` (uploads temp) > 85 % | Slack `#infra` |

**Dashboard:** Grafana panel showing job execution timeline, success rate, and error breakdown by `error_type`.

---

## 8. Future Enhancements (Out of Scope for v1)

- **Dynamic job schedule UI**: Allow admins to change cron expressions via API (requires validation against `croniter`).  
- **Email template versioning**: Store templates in DB with `version` column; tasks reference template UUID.  
- **Dead‑letter queue UI**: Expose `/api/v1/jobs/dead‑letter` to list and re‑enqueue failed tasks.  
- **Worker autoscaling**: Kubernetes HPA based on queue length (`celery_queue_depth`).  

---

**Compliance checklist:**  
- [x] OSFI B‑20 stress test embedded in monthly report logic.  
- [x] FINTRAC audit trail created by `flag_fintrac_overdue`.  
- [x] PIPEDA filters applied to logs; no SIN/DOB in job results.  
- [x] CMHC premium tiers stored as `Decimal` in JSONB.  
- [x] Immutable audit fields (`created_at`, `updated_at`) on all tables.  

**Next Steps:** Implement the module skeleton (`modules/jobs/…`) and create the Alembic revision. Then configure Celery beat to read schedules from `scheduled_jobs` table.