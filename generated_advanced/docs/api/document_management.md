# Document Management API

## POST /api/v1/documents

Upload a new document and associate it with a mortgage application.

**Request:**
```json
{
  "application_id": 123,
  "document_type": "government_id",
  "file_name": "driver_license_front.jpg",
  "file_size": 2048576,
  "mime_type": "image/jpeg"
}
```
*Note: The actual file binary is typically handled via `multipart/form-data` in the request body, but metadata is validated against this schema.*

**Response (201):**
```json
{
  "id": 501,
  "application_id": 123,
  "uploaded_by": 10,
  "document_type": "government_id",
  "file_name": "driver_license_front.jpg",
  "file_path": "/secure/uploads/app_123/doc_501.jpg",
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
- 422: Validation error (e.g., invalid `document_type`).

---

## GET /api/v1/documents

List documents for a specific application.

**Query Parameters:**
- `application_id` (integer, required): The ID of the mortgage application.
- `document_type` (string, optional): Filter by document type.

**Response (200):**
```json
[
  {
    "id": 501,
    "application_id": 123,
    "document_type": "government_id",
    "file_name": "driver_license_front.jpg",
    "status": "accepted",
    "is_verified": true,
    "uploaded_at": "2026-03-02T14:30:00Z"
  },
  {
    "id": 502,
    "application_id": 123,
    "document_type": "t4_slip",
    "file_name": "2024_t4.pdf",
    "status": "pending",
    "is_verified": false,
    "uploaded_at": "2026-03-02T15:00:00Z"
  }
]
```

---

## PATCH /api/v1/documents/{id}/verify

Verify a document. This action is auditable (FINTRAC compliance).

**Request:**
```json
{
  "is_verified": true
}
```

**Response (200):**
```json
{
  "id": 501,
  "is_verified": true,
  "verified_by": 20,
  "verified_at": "2026-03-02T16:00:00Z",
  "status": "accepted"
}
```

**Errors:**
- 403: User lacks permission to verify documents.
- 404: Document not found.

---

## PATCH /api/v1/documents/{id}/status

Update the status of a document (e.g., reject a document).

**Request:**
```json
{
  "status": "rejected",
  "rejection_reason": "Document is expired (issued > 5 years ago)."
}
```

**Response (200):**
```json
{
  "id": 502,
  "status": "rejected",
  "rejection_reason": "Document is expired (issued > 5 years ago).",
  "updated_at": "2026-03-02T16:15:00Z"
}
```

**Errors:**
- 400: Invalid status transition.

---

## GET /api/v1/document-requirements

Check required and received documents for a specific application.

**Query Parameters:**
- `application_id` (integer, required): The ID of the mortgage application.

**Response (200):**
```json
[
  {
    "id": 101,
    "application_id": 123,
    "document_type": "government_id",
    "is_required": true,
    "is_received": true,
    "due_date": "2026-03-15T00:00:00Z"
  },
  {
    "id": 102,
    "application_id": 123,
    "document_type": "proof_of_sin",
    "is_required": true,
    "is_received": false,
    "due_date": "2026-03-15T00:00:00Z"
  }
]
```

---

# Document Management Module

## Overview
The Document Management module handles the lifecycle of mortgage underwriting documents, including upload, storage, verification, and requirement tracking. It ensures compliance with **PIPEDA** (secure handling of PII) and **FINTRAC** (audit trails for identity verification).

## Key Functions

### 1. Document Upload & Storage
- **Function:** `upload_document(application_id, file, metadata)`
- **Description:** Accepts file uploads, validates MIME types and file sizes, and stores them securely. Files containing PII (e.g., `proof_of_sin`) are encrypted at rest.
- **Returns:** Document ID and metadata.

### 2. Requirement Tracking
- **Function:** `check_requirements(application_id)`
- **Description:** Compares required document types against uploaded documents to identify missing items (e.g., missing "pay_stub").
- **Returns:** List of fulfilled and unfulfilled requirements.

### 3. Verification Workflow
- **Function:** `verify_document(document_id, user_id)`
- **Description:** Marks a document as verified by an underwriter. Updates `verified_by` and `verified_at` timestamps to satisfy FINTRAC audit requirements.

## Usage Example

```python
import httpx

async def upload_income_doc():
    async with httpx.AsyncClient() as client:
        files = {
            'file': ('2023_t4.pdf', open('2023_t4.pdf', 'rb'), 'application/pdf')
        }
        data = {
            'application_id': '123',
            'document_type': 't4_slip'
        }
        response = await client.post(
            'http://api:8000/api/v1/documents',
            files=files,
            data=data
        )
    return response.json()
```

## Regulatory Notes
- **PIPEDA:** `proof_of_sin` documents trigger AES-256 encryption. File paths for these documents are obfuscated in logs.
- **FINTRAC:** All verification actions are immutable. `verified_by` and `verified_at` fields are never nullified once set.

---

# Configuration Notes

Update `.env.example` with the following variables:

```bash
# Document Management Configuration
# Directory where files are stored (absolute path recommended)
UPLOAD_DIR=/var/lib/mortgage_app/uploads

# Maximum file size in Megabytes
MAX_UPLOAD_SIZE_MB=10

# Allowed MIME types (comma separated)
ALLOWED_MIME_TYPES=image/jpeg,image/png,application/pdf

# Encryption key for PII documents (32 bytes for AES-256)
# Generate via: python -c "import secrets; print(secrets.token_urlsafe(32))"
PII_ENCRYPTION_KEY=change_me_in_production
```