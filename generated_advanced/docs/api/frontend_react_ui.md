# Frontend React UI API

## Overview
The Frontend React UI module serves the Single Page Application (SPA) and provides specific aggregation endpoints tailored for the UI views. This module handles file uploads, pipeline status tracking, and decision visualization data retrieval.

---

## POST /api/v1/frontend/documents

Upload borrower documents (PDFs) to the application intake queue.

**Request:**
`Content-Type: multipart/form-data`

```json
{
  "application_id": "uuid-v4",
  "document_type": "income_verification", // or 'id_verification', 'property_appraisal'
  "file": "<binary>"
}
```

**Response (201):**
```json
{
  "document_id": "uuid-v4",
  "status": "uploaded",
  "created_at": "2026-03-02T10:00:00Z"
}
```

**Errors:**
- 400: Invalid file type or size exceeded
- 401: Not authenticated
- 413: Payload too large

**Security Notes:**
- Documents are scanned for viruses before processing.
- PII extraction is handled asynchronously; raw files are encrypted at rest (AES-256).

---

## GET /api/v1/frontend/applications/{id}/status

Retrieve the current pipeline stage and progress for the Application Status page.

**Parameters:**
- `id` (path): Application UUID

**Response (200):**
```json
{
  "application_id": "uuid-v4",
  "current_stage": "policy_evaluation", // extraction, policy_evaluation, decision
  "progress_percent": 65,
  "last_updated": "2026-03-02T10:05:00Z",
  "estimated_completion": "2026-03-02T10:15:00Z"
}
```

**Errors:**
- 404: Application not found

---

## GET /api/v1/frontend/applications/{id}/decision

Retrieve detailed decision data, ratio breakdowns, and flags for the Decision Review page.

**Parameters:**
- `id` (path): Application UUID

**Response (200):**
```json
{
  "application_id": "uuid-v4",
  "decision": "approved", // approved, rejected, referred
  "gds_ratio": "28.50",
  "tds_ratio": "32.10",
  "stress_test_rate": "5.25",
  "ltv": "75.00",
  "insurance_required": false,
  "flags": [
    {
      "code": "HIGH_INCOME_VOLATILITY",
      "severity": "warning",
      "description": "Income varies >20% year-over-year"
    }
  ],
  "audit_trail": [
    {
      "timestamp": "2026-03-02T10:00:00Z",
      "action": "calculation_run",
      "user_id": "system"
    }
  ]
}
```

**Errors:**
- 404: Application not found
- 403: Decision not yet available

**Regulatory Compliance:**
- GDS/TDS calculations adhere to OSFI B-20 limits.
- Logs are created for every calculation step (auditability).

---

## GET /api/v1/frontend/exceptions

Retrieve the list of applications flagged for human review (Exception Queue).

**Query Parameters:**
- `status` (optional): `pending`, `reviewed`, `waived`
- `assignee` (optional): Filter by underwriter ID

**Response (200):**
```json
{
  "count": 1,
  "results": [
    {
      "exception_id": "uuid-v4",
      "application_id": "uuid-v4",
      "borrower_name": "Redacted", // PII masked
      "flag_reason": "Credit Score Mismatch",
      "severity": "critical",
      "created_at": "2026-03-02T09:30:00Z",
      "assigned_to": "underwriter_123"
    }
  ]
}
```

**Errors:**
- 401: Not authenticated

---

## GET /api/v1/frontend/config

Retrieve static configuration data for the UI (dropdowns, constants).

**Response (200):**
```json
{
  "lenders": [
    {"id": "lender_a", "name": "Bank of North"},
    {"id": "lender_b", "name": "Trust Canada"}
  ],
  "document_types": [
    {"value": "pay_stub", "label": "Pay Stub"},
    {"value": "t4", "label": "T4 Slip"}
  ],
  "max_upload_size_mb": 10
}
```

---

# Frontend React UI Module README

## Overview
The `frontend_ui` module serves the React Single Page Application (SPA) and provides specialized API endpoints that aggregate backend data for specific UI views. It handles the presentation layer logic, ensuring that the UI receives data in the exact format required by the components (e.g., charts, progress bars).

## Key Functions

### 1. Document Intake
- **Endpoint:** `POST /api/v1/frontend/documents`
- **Description:** Handles multipart file uploads. Interacts with the `storage` service to save encrypted files and triggers the `extraction` module to process PDF data.
- **Usage:** Used by the "Document Uploader" component on the Application Submission page.

### 2. Pipeline Orchestration
- **Endpoint:** `GET /api/v1/frontend/applications/{id}/status`
- **Description:** Aggregates events from the message bus (RabbitMQ/Kafka) to determine the real-time progress of an application through the underwriting pipeline.
- **Usage:** Used by the "Progress Indicators" component.

### 3. Decision Visualization
- **Endpoint:** `GET /api/v1/frontend/applications/{id}/decision`
- **Description:** Fetches the final underwriting decision and formats financial ratios (GDS/TDS/LTV) for charting libraries.
- **Usage:** Used by the "Decision Result Visualization" component.

### 4. Exception Management
- **Endpoint:** `GET /api/v1/frontend/exceptions`
- **Description:** Queries the `underwriting` module for records where `requires_manual_review = True`.
- **Usage:** Used by the "Exception Queue" page.

## Usage Examples

### Fetching Application Status for Progress Bar
```javascript
const response = await fetch(`/api/v1/frontend/applications/${appId}/status`);
const data = await response.json();
setProgress(data.progress_percent);
setStage(data.current_stage);
```

### Uploading a Document
```javascript
const formData = new FormData();
formData.append('file', file);
formData.append('application_id', appId);
formData.append('document_type', 'pay_stub');

await fetch('/api/v1/frontend/documents', {
  method: 'POST',
  body: formData
});
```

## PII Handling
This module ensures that:
1.  **PIPEDA Compliance:** No SIN or DOB is ever returned in API responses. Names are redacted in list views (Exception Queue).
2.  **Audit Trail:** Every document upload is logged with `created_at` and `user_id` for FINTRAC retention requirements.

---

# Configuration Notes

## Environment Variables

Add the following to `.env.example`:

```bash
# Frontend React UI Configuration

# URL where the React static assets are served (if using CDN)
FRONTEND_ASSET_URL=https://cdn.mortgage-system.com/ui/v1

# Maximum file upload size (bytes)
MAX_UPLOAD_SIZE=10485760

# Allowed MIME types for document upload
ALLOWED_DOCUMENT_TYPES=application/pdf,image/jpeg,image/png

# Feature flags
ENABLE_EXCEPTION_QUEUE=true
ENABLE_DECISION_CHARTS=true
```