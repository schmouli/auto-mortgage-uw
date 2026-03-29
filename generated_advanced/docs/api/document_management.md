# Document Management API

## Overview
The Document Management module handles the upload, storage, verification, and tracking of borrower documents. It ensures compliance with PIPEDA by managing metadata for encrypted files and supports the underwriting workflow by tracking required vs. received documents.

---

## POST /api/v1/documents

Upload a new document and associate it with a mortgage application.

**Request:**
```json
{
  "application_id": 101,
  "document_type": "IDENTITY.proof_of_sin",
  "file_name": "sin_card_front.jpg",
  "file_path": "/secure/storage/encrypted/a1b2c3d4.jpg",
  "file_size": 2048576,
  "mime_type": "image/jpeg"
}
```

**Response (201):**
```json
{
  "id": 5001,
  "application_id": 101,
  "uploaded_by": 42,
  "document_type": "IDENTITY.proof_of_sin",
  "file_name": "sin_card_front.jpg",
  "file_path": "/secure/storage/encrypted/a1b2c3d4.jpg",
  "file_size": 2048576,
  "mime_type": "image/jpeg",
  "status": "pending",
  "is_verified": false,
  "uploaded_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 400: Invalid file type or size exceeds limit.
- 404: Application not found.
- 422: Validation error (e.g., invalid `document_type` enum).

---

## GET /api/v1/documents

Retrieve a list of documents, optionally filtered by application or status.

**Query Parameters:**
- `application_id` (int, optional): Filter by mortgage application.
- `status` (str, optional): Filter by status (`pending`, `accepted`, `rejected`).

**Response (200):**
```json
[
  {
    "id": 5001,
    "application_id": 101,
    "document_type": "INCOME.t4_slip",
    "file_name": "2024_t4.pdf",
    "status": "accepted",
    "is_verified": true,
    "verified_by": 15,
    "verified_at": "2026-03-02T15:00:00Z"
  }
]
```

---

## PATCH /api/v1/documents/{id}/verify

Verify or reject a document. This action is performed by an underwriter.

**Request:**
```json
{
  "status": "accepted",
  "rejection_reason": null
}
```

**Response (200):**
```json
{
  "id": 5001,
  "status": "accepted",
  "is_verified": true,
  "verified_by": 15,
  "verified_at": "2026-03-02T16:45:00Z"
}
```

**Errors:**
- 400: Cannot verify an already verified document.
- 404: Document not found.
- 422: `rejection_reason` is required when status is `rejected`.

---

## GET /api/v1/applications/{application_id}/requirements

Check the document requirements checklist for a specific application.

**Response (200):**
```json
[
  {
    "id": 1,
    "application_id": 101,
    "document_type": "INCOME.employment_letter",
    "is_required": true,
    "is_received": false,
    "due_date": "2026-03-15T23:59:59Z"
  },
  {
    "id": 2,
    "application_id": 101,
    "document_type": "IDENTITY.government_id",
    "is_required": true,
    "is_received": true,
    "due_date": "2026-03-01T23:59:59Z"
  }
]
```

---

# Module README: Document Management

## Overview
This module manages the lifecycle of borrower documentation within the Canadian Mortgage Underwriting System. It separates the storage of file metadata from the actual file content (which is stored in an encrypted blob store). It enforces strict audit trails (FINTRAC) by tracking who uploaded and verified specific documents.

## Key Functions

1.  **Document Upload & Tracking**
    *   Associates files with `application_id`.
    *   Validates `document_type` against allowed enums (e.g., `IDENTITY.proof_of_sin`, `INCOME.noa`).
    *   Sets initial status to `pending`.

2.  **Verification Workflow**
    *   Allows underwriters to mark documents as `accepted` or `rejected`.
    *   Enforces `rejection_reason` logging for rejected documents.
    *   Updates `document_requirements` automatically when a new document of a specific type is uploaded.

3.  **Compliance & Audit**
    *   **PIPEDA:** File paths point to AES-256 encrypted storage. Sensitive file types (like SIN proof) are flagged internally for strict access control.
    *   **FINTRAC:** All records are immutable (no deletes) and include `created_at`/`updated_at` timestamps.

## Usage Example

```python
import httpx

async def upload_income_document():
    async with httpx.AsyncClient() as client:
        payload = {
            "application_id": 101,
            "document_type": "INCOME.pay_stub",
            "file_name": "february_paystub.pdf",
            "file_path": "s3://secure-bucket/enc/xyz.pdf",
            "file_size": 102400,
            "mime_type": "application/pdf"
        }
        response = await client.post(
            "http://api:8000/api/v1/documents",
            json=payload,
            headers={"Authorization": "Bearer <token>"}
        )
        return response.json()
```

---

# Configuration Notes

## Environment Variables

Add the following to `.env.example`:

```bash
# Document Management Configuration
# Storage backend: 'local' or 's3'
DOCUMENT_STORAGE_BACKEND=local

# Local path for encrypted file storage (if backend is local)
DOCUMENT_STORAGE_PATH=./data/secure_docs

# AWS S3 Bucket name (if backend is s3)
AWS_S3_DOCUMENT_BUCKET=mortgage-docs-prod

# Maximum file upload size in bytes (e.g., 25MB)
MAX_DOCUMENT_SIZE=26214400

# Allowed MIME types (comma separated)
ALLOWED_MIME_TYPES=application/pdf,image/jpeg,image/png
```

---

# CHANGELOG.md Entry

```markdown
## [2026-03-02]
### Added
- Document Management: New endpoints for uploading and tracking borrower documents.
- Document Verification: Endpoints for underwriters to accept/reject documents.
- Document Requirements: API to check required vs. received documents per application.

### Changed
- Updated application schema to support document status aggregation.
```