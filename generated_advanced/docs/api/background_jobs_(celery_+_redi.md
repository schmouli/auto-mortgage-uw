# Background Jobs (Celery + Redis)

## API Documentation

### POST /api/v1/background-jobs/trigger

Manually trigger a specific background task (Admin only). Useful for immediate execution outside of the scheduled cron window.

**Request:**
```json
{
  "task_name": "send_document_reminder",
  "kwargs": {}
}
```

**Response (202 Accepted):**
```json
{
  "detail": "Task 'send_document_reminder' queued successfully",
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Errors:**
- 401: Not authenticated
- 403: Permission denied (Admin role required)
- 404: Task name not found in registry
- 422: Validation error in kwargs

---

### GET /api/v1/background-jobs/status

Check the health and status of the Celery workers.

**Response (200 OK):**
```json
{
  "status": "online",
  "workers": [
    {
      "name": "celery@worker1",
      "status": "online",
      "active_tasks": 1,
      "queue": "default"
    }
  ],
  "timestamp": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 503: Service unavailable (Redis connection failed)

---

### GET /api/v1/background-jobs/result/{task_id}

Retrieve the result or status of an asynchronous task.

**Response (200 OK):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUCCESS",
  "result": {
    "processed": 15,
    "failed": 0
  },
  "date_done": "2026-03-02T10:05:00Z"
}
```

**Errors:**
- 404: Task ID not found or expired

---

## Module README

### Overview
The **Background Jobs** module handles asynchronous and scheduled tasks using **Celery** and **Redis**. It ensures that long-running processes, such as email notifications, data cleanup, and financial reporting, do not block the main API thread.

### Scheduled Tasks
The following tasks are automated via Celery Beat:

| Task Name | Schedule | Description |
| :--- | :--- | :--- |
| **send_document_reminder** | Daily 9:00 AM | Queries for clients with outstanding document requirements and sends email reminders. Ensures PII is not logged. |
| **check_rate_expiry** | Daily 7:00 AM | Scans `lender_products` to identify products with expired interest rates and flags them in the database. |
| **check_condition_due_dates** | Daily 8:00 AM | Identifies overdue lender conditions on applications and updates their status to `OVERDUE`. |
| **generate_monthly_report** | 1st of Month, 6:00 AM | Aggregates financial data for the previous month (using `Decimal` for precision) and stores the report record. |
| **cleanup_temp_uploads** | Daily 2:00 AM | Scans the `/uploads/temp` directory and deletes files older than 24 hours to comply with PIPEDA data minimization. |
| **flag_fintrac_overdue** | Daily 9:00 AM | Checks applications for missing FINTRAC verification. Flags violations and creates an immutable audit log entry. |

### Key Functions
*   **Task Registration:** All tasks are registered in `modules/background_jobs/celery_app.py`.
*   **Error Handling:** Failed tasks trigger alerts via structlog and are retried with exponential backoff (max 3 retries).
*   **Compliance:**
    *   **FINTRAC:** The `flag_fintrac_overdue` task strictly enforces audit logging.
    *   **PIPEDA:** `cleanup_temp_uploads` ensures temporary PII is purged.

### Usage Examples

**Triggering a task manually via code:**
```python
from modules.background_jobs.services import send_document_reminder

# Trigger immediately
send_document_reminder.delay()

# Trigger with specific arguments (if supported)
send_document_reminder.apply_async(args=[], countdown=60)
```

---

## Configuration Notes

### Environment Variables

Add the following to your `.env` file to configure the Celery workers and Redis connection.

```bash
# Background Jobs (Celery + Redis) Configuration

# Redis connection string (Format: redis://[:password@]localhost[:port][/db_number])
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Timezone for scheduled tasks (CRON)
CELERY_TIMEZONE=America/Toronto

# Task settings
CELERY_TASK_TRACK_STARTED=True
CELERY_TASK_TIME_LIMIT=30*60  # Hard limit: 30 minutes per task
CELERY_TASK_SOFT_TIME_LIMIT=25*60 # Soft limit: 25 minutes (raises exception)

# Email settings (required for send_document_reminder)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@mortgage-system.com
SMTP_PASSWORD=secure_password
```

### Deployment Instructions

1.  **Start Redis:** Ensure a Redis instance is running and accessible.
2.  **Start Celery Worker:**
    ```bash
    uv run celery -A modules.background_jobs.celery_app worker --loglevel=info --concurrency=4
    ```
3.  **Start Celery Beat (Scheduler):**
    ```bash
    uv run celery -A modules.background_jobs.celery_app beat --loglevel=info
    ```

---

## [2026-03-02]

### Added
- **Background Jobs (Celery + Redis):** New module for asynchronous task processing.
- **Scheduled Tasks:** Implemented `send_document_reminder`, `check_rate_expiry`, `check_condition_due_dates`, `generate_monthly_report`, `cleanup_temp_uploads`, and `flag_fintrac_overdue`.
- **Admin Endpoints:** Added routes to trigger jobs manually and check worker status (`/api/v1/background-jobs/`).

### Changed
- Updated infrastructure dependencies to include `celery` and `redis`.

---

## .env.example Update

```bash
# ... existing config ...

# Background Jobs (Celery + Redis) Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TIMEZONE=America/Toronto
CELERY_TASK_TRACK_STARTED=True
CELERY_TASK_TIME_LIMIT=1800
CELERY_TASK_SOFT_TIME_LIMIT=1500
```