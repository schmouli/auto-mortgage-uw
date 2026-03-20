```markdown
# Frontend React UI API

## Module Overview

The **Frontend React UI** module serves as the backend API interface for the React-based user interface. It facilitates the mortgage application workflow by handling document submissions, tracking pipeline status, exposing decision details, and managing the exception queue for human review.

This module acts as the bridge between the React client and the core underwriting engine, ensuring data is transmitted securely and efficiently while adhering to OSFI B-20, FINTRAC, and PIPEDA regulations.

### Key Functions

- **Application Submission:** Ingests borrower metadata and uploaded PDF documents (income verification, identity, property appraisal).
- **Pipeline Tracking:** Provides real-time status updates as applications move through extraction, policy validation, and decisioning stages.
- **Decision Visualization:** Supplies detailed breakdowns of GDS/TDS ratios, LTV calculations, and risk flags for the UI to render charts.
- **Exception Management:** Retrieves applications flagged for manual review, allowing underwriters to override or correct data.

### Configuration Notes

To support file uploads and CORS for the React frontend, ensure the following environment variables are configured in `.env`:

```bash
# Frontend React UI Configuration

# CORS settings (comma-separated list of allowed origins)
FRONTEND_ALLOWED_ORIGINS=http://localhost:3000,https://mortgage-app.example.com

# File Upload Constraints
MAX_UPLOAD_SIZE_MB=10
ALLOWED_DOCUMENT_TYPES=application/pdf,image/jpeg,image/png

# Storage (S3 or local path for uploaded PDFs)
DOCUMENT_STORAGE_PATH=./data/uploads
# or S3_BUCKET_NAME=underwriting-docs-prod

# Pipeline Settings
PIPELINE_POLL_INTERVAL_SECONDS=5
```

---

## API Endpoints

### POST /api/v1/frontend/applications

Initiates a new mortgage application. This endpoint accepts borrower metadata and references to uploaded documents.

**Request:**
```json
{
  "lender_id": "uuid-lender-123",
  "borrower_info": {
    "first_name": "Jane",
    "last_name": "Doe",
    "date_of_birth": "1990-01-15",
    "sin_hash": "a1b2c3d4e5f6..."
  },
  "property_details": {
    "address": "123 Maple St",
    "city": "Toronto",
    "province": "ON",
    "postal_code": "M5V 1A1",
    "purchase_price": "750000.00",
    "down_payment": "150000.00"
  },
  "loan_details": {
    "requested_amount": "600000.00",
    "amortization_years": 25,
    "interest_rate": "5.00",
    "term_years": 5
  },
  "document_ids": [
    "doc-uuid-1",
    "doc-uuid-2"
  ]
}
```

**Response (201):**
```json
{
  "application_id": "app-uuid-987",
  "status": "Received",
  "created_at": "2026-03-02T10:00:00Z",
  "message": "Application queued for processing"
}
```

**Errors:**
- `400`: Invalid financial value or missing required field.
- `413`: Payload size exceeds `MAX_UPLOAD_SIZE_MB`.
- `422`: Validation error (e.g., LTV > 95% or invalid SIN format).

---

### GET /api/v1/frontend/applications/{application_id}/status

Retrieves the current progress of the application through the underwriting pipeline.

**Response (200):**
```json
{
  "application_id": "app-uuid-987",
  "current_stage": "Policy_Engine", // Options: Extraction, Policy_Engine, Decisioning, Completed
  "stage_progress": 65, // Percentage 0-100
  "estimated_completion": "2026-03-02T10:05:00Z",
  "is_flagged": false
}
```

**Errors:**
- `404`: Application not found.

---

### GET /api/v1/frontend/applications/{application_id}/decision

Fetches the final underwriting decision, including ratio breakdowns and audit trail for the Review page.

**Response (200):**
```json
{
  "application_id": "app-uuid-987",
  "decision": "Approved", // Options: Approved, Rejected, Referred
  "qualifying_rate": "7.00", // max(contract_rate + 2%, 5.25%)
  "financials": {
    "loan_amount": "600000.00",
    "property_value": "750000.00",
    "ltv": "80.00",
    "insurance_required": false,
    "monthly_piti": "3500.00",
    "gds": "28.50", // <= 39%
    "tds": "35.00"  // <= 44%
  },
  "flags": [],
  "audit_trail": [
    {
      "timestamp": "2026-03-02T10:01:00Z",
      "actor": "system",
      "action": "GDS/TDS Calculation",
      "details": "Calculated at qualifying rate 7.00%"
    }
  ]
}
```

**Errors:**
- `404`: Application not found.
- `400`: Decision not yet available.

---

### GET /api/v1/frontend/exceptions

Retrieves a list of applications flagged for human underwriter review (Exception Queue).

**Query Parameters:**
- `status`: (optional) Filter by `pending_review`, `reviewed`, `overridden`.
- `limit`: (optional) Number of results (default 50).

**Response (200):**
```json
{
  "count": 1,
  "results": [
    {
      "application_id": "app-uuid-999",
      "borrower_name": "John Smith",
      "flagged_reason": "Income Discrepancy",
      "flagged_at": "2026-03-02T09:30:00Z",
      "priority": "High"
    }
  ]
}
```

**Errors:**
- `401`: Not authenticated (Underwriter role required).

---

### POST /api/v1/frontend/applications/{application_id}/override

Allows an underwriter to override a system decision or correct data for a flagged application.

**Request:**
```json
{
  "underwriter_id": "user-uuid-123",
  "override_reason": "Verified income via paystub addendum",
  "updated_field": "annual_income",
  "new_value": "120000.00",
  "notes": "Applicant provided bonus documentation not parsed initially."
}
```

**Response (200):**
```json
{
  "application_id": "app-uuid-999",
  "status": "Reprocessing",
  "message": "Override applied. Application re-queued for decisioning."
}
```

**Errors:**
- `403`: User lacks underwriter permissions.
- `404`: Application not found.
- `422`: Invalid override data or logic violation.

---

### GET /api/v1/frontend/applications/{application_id}/audit

Retrieves the full immutable audit trail for a specific application (FINTRAC compliance).

**Response (200):**
```json
{
  "application_id": "app-uuid-987",
  "created_at": "2026-03-02T10:00:00Z",
  "history": [
    {
      "timestamp": "2026-03-02T10:00:01Z",
      "actor": "system",
      "action": "Application Created",
      "details": "Initial submission via Web UI"
    },
    {
      "timestamp": "2026-03-02T10:01:15Z",
      "actor": "system",
      "action": "Identity Verification",
      "details": "SIN hash matched against government DB"
    }
  ]
}
```

**Errors:**
- `401`: Not authenticated.
- `404`: Application not found.
```