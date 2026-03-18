# Background Jobs (Celery + Redis) API

## POST /api/v1/background-jobs/trigger

Manually trigger a specific background job (Admin only). Useful for debugging or immediate execution outside the schedule.

**Request:**
```json
{
  "job_name": "send_document_reminder",
  "parameters": {
    "applicant_id": 42
  }
}
```

**Response (202):**
```json
{
  "task_id": "a1b2c3d4-5678-90ef-ghij-klmnopqrstuv",
  "status": "PENDING",
  "message": "Job 'send_document_reminder' queued successfully"
}
```

**Errors:**
- 400: Invalid job name or parameters
- 401: Not authenticated
- 403: Permission denied (Admin role required)

---

## GET /api/v1/background-jobs/status

Check the health status of the Celery worker and active tasks.

**Response (200):**
```json
{
  "status": "healthy",
  "celery_status": "ok",
  "active_tasks": 3,
  "scheduled_tasks_count": 6
}
```

**Errors:**
- 503: Service unavailable (Redis connection failed)

---

# Background Jobs Module

## Overview
The Background Jobs module handles asynchronous and scheduled tasks using **Celery** with **Redis** as the message broker and result backend. This ensures that long-running processes (like reporting or batch updates) do not block the main API thread.

## Key Functions & Scheduled Tasks

This module manages the following cron-scheduled jobs:

| Job Name | Schedule | Description |
| :--- | :--- | :--- |
| `cleanup_temp_uploads` | Daily 2AM | Deletes temporary files in `/uploads/temp` older than 24 hours. (PIPEDA Compliance: Data Minimization) |
| `check_rate_expiry` | Daily 7AM | Flags lender products in the database where the posted expiry date has passed. |
| `check_condition_due_dates` | Daily 8AM | Identifies and flags overdue conditions attached to lender approvals. |
| `generate_monthly_report` | 1st of Month, 6AM | Aggregates underwriting data for the previous month and stores the record. (OSFI Compliance: Auditable logs) |
| `send_document_reminder` | Daily 9AM | Sends email notifications to applicants with outstanding document requirements. |
| `flag_fintrac_overdue` | Daily 9AM | Scans for applications missing mandatory FINTRAC identity verification and flags them for review. (FINTRAC Compliance) |

## Usage Examples

### Defining a Task
Tasks are defined in `modules/background_jobs/tasks.py`.

```python
from celery import Celery

celery_app = Celery("underwriting", broker="redis://localhost:6379/0")

@celery_app.task(name="send_document_reminder")
def send_document_reminder():
    # Logic to query DB and send emails
    pass
```

### Triggering a Job Programmatically
While jobs run on a schedule, they can also be triggered via code:

```python
from modules.background_jobs.tasks import send_document_reminder

# Trigger async
send_document_reminder.delay()

# Trigger with parameters
send_document_reminder.apply_async(args=[applicant_id], countdown=60)
```

## Infrastructure Notes
- **Broker:** Redis (required for queuing).
- **Worker:** Must be running separately from the API process (`uv run celery -A modules.background_jobs.worker worker --loglevel=info`).
- **Beat Scheduler:** Must be running to handle cron schedules (`uv run celery -A modules.background_jobs.worker beat --loglevel=info`).

---

# CHANGELOG.md

```markdown
## [2026-03-02]
### Added
- Background Jobs (Celery + Redis): New module for asynchronous task processing.
- Implemented 6 scheduled jobs: send_document_reminder, check_rate_expiry, check_condition_due_dates, generate_monthly_report, cleanup_temp_uploads, flag_fintrac_overdue.
- Added administrative endpoints to trigger jobs manually and check worker status.

### Changed
- Updated project dependencies to include celery and redis.
```

---

# .env.example

```bash
# Background Jobs (Celery + Redis) Configuration

# Redis connection string for Celery Broker and Backend
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Timezone for scheduled tasks (Celery Beat)
CELERY_TIMEZONE=America/Toronto

# Task result expiration (in seconds)
CELERY_RESULT_EXPIRES=3600

# Task serialization format (json is required for security vs pickle)
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_ACCEPT_CONTENT=json
```