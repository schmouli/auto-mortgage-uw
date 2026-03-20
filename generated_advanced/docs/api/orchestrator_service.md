# Orchestrator Service Documentation

## Module Overview

The **Orchestrator Service** acts as the single entry point for the Canadian Mortgage Underwriting System. It coordinates the full underwriting pipeline by accepting application submissions, managing document storage (MinIO/S3), dispatching asynchronous processing tasks via Celery, and serving the final decision results to the frontend.

### Key Responsibilities
- **Submission Handling:** Ingests mortgage applications including PDF document uploads and lender selection.
- **Task Orchestration:** Dispatches a chain of Celery tasks (`extract_documents` → `evaluate_policy` → `run_decision`).
- **State Management:** Tracks the status of long-running underwriting processes.
- **Compliance:** Ensures audit trails (FINTRAC) are created for every submission and handles PII securely (PIPEDA) during handoffs.

### Workflow
1. Frontend uploads application data + documents.
2. Orchestrator validates input and uploads documents to MinIO.
3. Orchestrator creates a database record and triggers a Celery chain.
4. Worker nodes execute pipeline steps (OCR, Rules Engine, Decisioning).
5. Frontend polls for status or retrieves final decision.

---

## API Documentation

### POST /api/v1/orchestrator/applications

Initiates a new mortgage application. Accepts multipart form data for document upload and JSON metadata for the application details.

**Request:**
*   **Content-Type:** `multipart/form-data`
*   **Body:**
    *   `documents`: File(s) (e.g., `application.pdf`)
    *   `metadata`: JSON string
        ```json
        {
          "lender_id": "uuid-string",
          "applicant_name": "John Doe",
          "requested_amount": "450000.00",
          "property_value": "500000.00"
        }
        ```

**Response (202 Accepted):**
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSING",
  "message": "Application received and queued for underwriting",
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `400`: Invalid file format or missing metadata.
- `422`: Validation error (e.g., `requested_amount` must be positive Decimal).
- `401`: Not authenticated.

---

### GET /api/v1/orchestrator/applications/{application_id}/status

Retrieves the current processing status of the application. This is used for polling the frontend while Celery tasks run.

**Parameters:**
- `application_id` (path): UUID of the application.

**Response (200 OK):**
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED", // PENDING, PROCESSING, COMPLETED, FAILED
  "current_step": "run_decision",
  "updated_at": "2026-03-02T10:05:00Z"
}
```

**Errors:**
- `404`: Application not found.

---

### GET /api/v1/orchestrator/applications/{application_id}

Retrieves the final underwriting decision and detailed breakdown. Only available when status is `COMPLETED`.

**Parameters:**
- `application_id` (path): UUID of the application.

**Response (200 OK):**
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "APPROVED", // APPROVED, REJECTED, REFER
  "lender_id": "uuid-string",
  "financials": {
    "loan_amount": "450000.00",
    "ltv": "90.00",
    "insurance_required": true,
    "gds": "28.50",
    "tds": "35.20",
    "qualifying_rate": "7.25"
  },
  "audit": {
    "created_at": "2026-03-02T10:00:00Z",
    "completed_at": "2026-03-02T10:05:00Z"
  }
}
```

**Errors:**
- `404`: Application not found.
- `425`: Too Early (Decision not yet ready).

---

## Configuration Notes

This module requires configuration for the message broker (Celery) and object storage (MinIO/S3).

### Environment Variables

Add the following to `.env.example`:

```bash
# Orchestrator Service Configuration

# Celery Configuration (Redis or RabbitMQ)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Object Storage (MinIO or S3)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=mortgage-docs
MINIO_SECURE=false

# Pipeline Settings
MAX_FILE_SIZE_MB=10
ALLOWED_FILE_TYPES=.pdf,.png,.jpg
```

### Dependencies
Ensure the following are installed in `pyproject.toml`:
- `celery`
- `redis` (if using Redis as broker)
- `boto3` (for S3/MinIO interaction)
- `python-multipart` (for FastAPI file uploads)

### Audit & Compliance Notes
- **FINTRAC:** The `submit` endpoint creates an immutable record in PostgreSQL with `created_at` timestamps. Document uploads are logged with correlation IDs.
- **PIPEDA:** Uploaded documents are stored securely in MinIO. PII extracted during the `extract_documents` task is encrypted at rest in the database before being persisted.