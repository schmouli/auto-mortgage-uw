# Orchestrator Service API

## Overview

The Orchestrator Service acts as the single entry point for the Canadian Mortgage Underwriting System. It manages the asynchronous pipeline by coordinating document ingestion (MinIO/S3), background task execution (Celery), and result aggregation (PostgreSQL).

## POST /api/v1/orchestrator/applications

Initiates a new mortgage application workflow. This endpoint accepts the application data and associated documents, uploads the files to object storage, and dispatches a Celery chain to process the underwriting logic.

**Request:**
Content-Type: `multipart/form-data`

| Field | Type | Description |
|-------|------|-------------|
| `application_data` | JSON string | Stringified JSON containing applicant info and loan details. |
| `documents` | File List | List of PDF files (e.g., ID, Proof of Income, Property Appraisal). |

`application_data` JSON structure:
```json
{
  "lender_id": "uuid-string",
  "applicant": {
    "first_name": "John",
    "last_name": "Doe",
    "sin_hash": "sha256-hash-here",
    "date_of_birth": "1990-01-01"
  },
  "loan_details": {
    "principal_amount": "450000.00",
    "amortization_period_years": 25,
    "interest_rate": "5.00",
    "property_value": "500000.00"
  }
}
```

**Response (202 Accepted):**
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSING",
  "message": "Application received and documents uploaded. Underwriting in progress.",
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- `400 Bad Request`: Invalid file format or malformed JSON.
- `401 Unauthorized`: Invalid or missing authentication token.
- `422 Unprocessable Entity`: Validation error (e.g., missing required fields).
  ```json
  {
    "detail": "Principal amount must be positive",
    "error_code": "INVALID_FINANCIAL_VALUE"
  }
  ```

---

## GET /api/v1/orchestrator/applications/{application_id}

Retrieves the current status and decision details of a specific application.

**Request:**
Path Parameters:
- `application_id` (string): The UUID of the application.

**Response (200 OK):**
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "decision": "APPROVED",
  "details": {
    "gds_ratio": "28.50",
    "tds_ratio": "35.20",
    "ltv_ratio": "90.00",
    "insurance_required": true,
    "premium_rate": "3.10",
    "qualifying_rate": "7.00"
  },
  "updated_at": "2026-03-02T10:05:00Z"
}
```

**Errors:**
- `404 Not Found`: Application ID does not exist.
- `401 Unauthorized`: Invalid or missing authentication token.

---

# Module README: Orchestrator Service

## Key Functions

The Orchestrator Service is responsible for state management and workflow coordination. It does not contain business logic regarding GDS/TDS calculations or policy rules (those are handled by the `policy_engine` and `underwriting` modules). Instead, it:

1.  **Ingestion:** Validates incoming request structure and uploads PDF documents to MinIO/S3.
2.  **Dispatch:** Triggers the Celery task chain:
    *   `extract_documents`: OCR and data extraction.
    *   `evaluate_policy`: Runs business rules against extracted data.
    *   `run_decision`: Finalizes the approval/rejection status.
3.  **Persistence:** Saves the initial application state and updates the final decision in PostgreSQL.

## Usage Example

1.  **Submit Application:** The frontend sends a `POST` request with the applicant's financial data and supporting documents.
2.  **Polling:** The frontend uses the returned `application_id` to poll the `GET /applications/{application_id}` endpoint every few seconds.
3.  **Completion:** Once `status` is `COMPLETED`, the frontend displays the `decision` and the calculated financial ratios (`gds`, `tds`, `ltv`).

## Architecture Notes

- **Async Processing:** All heavy lifting is offloaded to Celery workers to keep the API responsive.
- **Idempotency:** Submissions are tracked by UUID to prevent duplicate processing.
- **Compliance:** While this module orchestrates, it ensures that all audit logs (created_by, timestamps) are attached to the application record in the database to satisfy FINTRAC requirements.

---

# Configuration Notes

## Environment Variables

The Orchestrator Service requires the following environment variables to be set in `.env`:

```bash
# Orchestrator Service Configuration
# -----------------------------

# Object Storage (MinIO or S3)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
MINIO_BUCKET_NAME=mortgage-docs

# Celery Configuration (Redis/RabbitMQ)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Task Settings
DOCUMENT_EXTRACTION_QUEUE=document_worker
UNDERWRITING_QUEUE=decision_worker
```

## Dependencies

This module relies on:
- `fastapi`: API framework.
- `celery`: Distributed task queue.
- `minio`: S3 compatible client for document storage.
- `sqlalchemy`: Database ORM.

---

## [2026-03-02]
### Added
- **Orchestrator Service**: New endpoints for submitting mortgage applications and checking status.
- **Document Upload**: Integration with MinIO/S3 for storing PDF evidence.
- **Async Pipeline**: Celery task implementation for document extraction and policy evaluation.

### Changed
- Updated common configuration to support Celery broker URLs.

### Fixed
- N/A (Initial release)