Here is the documentation for the Document Management module, split into the requested components.

### 1. API Documentation
**File:** `docs/api/document_management.md`

```markdown
# Document Management API

This module handles the uploading, tracking, and verification of borrower documents. It ensures compliance with PIPEDA for sensitive data storage and FINTRAC requirements for audit trails.

## Document Types

Documents are categorized as follows:

*   **IDENTITY**
    *   `government_id`
    *   `proof_of_sin`
*   **INCOME**
    *   `t4_slip`
    *   `noa` (Notice of Assessment)
    *   `pay_stub`
    *   `employment_letter`
    *   `t1_general`
    *   `financial_statement`

---

## POST /api/v1/documents

Uploads a new document and associates it with a mortgage application.

**Request:**
```json
{
  "application_id": 123,
  "document_type": "government_id",
  "file_name": "passport_scan.pdf",
  "file_data": "<base64_encoded_string>",
  "mime_type": "application/pdf"
}
```

**Response (201):**
```json
{
  "id": 456,
  "application_id": 123,
  "uploaded_by": 1,
  "document_type": "government_id",
  "file_name": "passport_scan.pdf",
  "file_path": "/secure/storage/456_passport_scan.pdf",
  "file_size": 1024000,
  "mime_type": "application/pdf",
  "status": "pending",
  "is_verified": false,
  "uploaded_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
*   400: Invalid file type or size exceeds limits.
*   401: Not authenticated.
*   404: Application not found.
*   422: Validation error (e.g., invalid `document_type`).

---

## GET /api/v1/applications/{application_id}/documents

Retrieves all documents associated with a specific application.

**Response (200):**
```json
[
  {
    "id": 456,
    "document_type": "government_id",
    "file_name": "passport_scan.pdf",
    "status": "accepted",
    "is_verified": true,
    "verified_at": "2026-03-02T15:00:00Z"
  },
  {
    "id": 457,
    "document_type": "pay_stub",
    "file_name": "january_paystub.pdf",
    "status": "pending",
    "is_verified": false
  }
]
```

**Errors:**
*   401: Not authenticated.
*   403: User does not have access to this application.

---

## GET /api/v1/documents/{document_id}

Retrieves metadata for a specific document. Note: The actual file content is not returned via this endpoint; a secure download URL or stream mechanism should be used separately.

**Response (200):**
```json
{
  "id": 456,
  "application_id": 123,
  "uploaded_by": 1,
  "document_type": "government_id",
  "file_name": "passport_scan.pdf",
  "file_size": 1024000,
  "status": "pending",
  "is_verified": false,
  "uploaded_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
*   401: Not authenticated.
*   404: Document not found.

---

## PATCH /api/v1/documents/{document_id}

Updates the status of a document (e.g., verification or rejection). Used by underwriters.

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
  "id": 456,
  "status": "accepted",
  "is_verified": true,
  "verified_by": 99,
  "verified_at": "2026-03-02T16:00:00Z",
  "rejection_reason": null
}
```

**Errors:**
*   400: Cannot transition status from 'rejected' to 'accepted' without re-upload.
*   401: Not authenticated.
*   403: User lacks underwriter permissions.
*   404: Document not found.

---

## GET /api/v1/applications/{application_id}/requirements

Retrieves the document requirement checklist for an application, indicating which documents are required and which have been received.

**Response (200):**
```json
[
  {
    "id": 1,
    "document_type": "government_id",
    "is_required": true,
    "is_received": true,
    "due_date": "2026-03-15T00:00:00Z"
  },
  {
    "id": 2,
    "document_type": "t4_slip",
    "is_required": true,
    "is_received": false,
    "due_date": "2026-03-15T00:00:00Z"
  }
]
```

**Errors:**
*   401: Not authenticated.
*   404: Application not found.
```

### 2. Module README
**File:** `docs/modules/document_management.md`

```markdown
# Document Management Module

## Overview
The Document Management module is responsible for the lifecycle of borrower documentation within the mortgage underwriting system. It handles file ingestion, storage, metadata tracking, and the verification workflow required by underwriters.

## Key Functions

### 1. Document Upload & Storage
*   **Endpoint:** `POST /api/v1/documents`
*   **Logic:** Accepts file uploads (via Base64 or multipart form-data), validates MIME types, and stores files securely.
*   **Security:** Files containing PII (e.g., SIN, DOB) are encrypted at rest using AES-256. File paths are stored in the database, but content is never logged.

### 2. Verification Workflow
*   **Endpoint:** `PATCH /api/v1/documents/{id}`
*   **Logic:** Allows authorized users (underwriters) to mark documents as `accepted` or `rejected`.
*   **Audit:** Automatically captures `verified_by` (user ID) and `verified_at` timestamps to satisfy FINTRAC audit trail requirements.

### 3. Requirement Tracking
*   **Endpoint:** `GET /api/v1/applications/{id}/requirements`
*   **Logic:** Dynamically checks which documents are required for a specific application stage and compares them against uploaded documents to provide a "Received/Not Received" status.

## Usage Example

### Uploading a Proof of SIN
```python
import httpx

async def upload_sin_document(application_id: int, file_path: str):
    async with httpx.AsyncClient() as client:
        with open(file_path, "rb") as f:
            files = {"file": ("sin.pdf", f, "application/pdf")}
            data = {
                "application_id": application_id,
                "document_type": "proof_of_sin"
            }
            response = await client.post(
                "http://api:8000/api/v1/documents",
                data=data,
                files=files
            )
    return response.json()
```

### Verifying a Document
```python
import httpx

async def verify_document(document_id: int, underwriter_token: str):
    async with httpx.AsyncClient() as client:
        payload = {"status": "accepted"}
        headers = {"Authorization": f"Bearer {underwriter_token}"}
        response = await client.patch(
            f"http://api:8000/api/v1/documents/{document_id}",
            json=payload,
            headers=headers
        )
    return response.json()
```

## Compliance Notes
*   **PIPEDA:** `proof_of_sin` documents are flagged for high-security storage. Access logs are strictly maintained.
*   **FINTRAC:** All document records are immutable. If a document needs to be replaced, a new record is created, and the old one is soft-deleted or marked as superseded (retained for 5 years).
```

### 3. Configuration Notes & Environment Variables

**File:** `.env.example` (Additions)

```bash
# Document Management Configuration
# Directory or S3 bucket path for encrypted storage
DOCUMENT_STORAGE_PATH=/var/lib/mortgage_docs

# Maximum file upload size in bytes (e.g., 25MB)
MAX_UPLOAD_SIZE=26214400

# Allowed MIME types for upload (comma separated)
ALLOWED_MIME_TYPES=application/pdf,image/jpeg,image/png

# Encryption key for AES-256 at-rest encryption (Must be 32 bytes)
DOCUMENT_ENCRYPTION_KEY=your-32-byte-encryption-key-here-change-me

# Number of days to retain soft-deleted documents (FINTRAC 5-year requirement)
DOCUMENT_RETENTION_DAYS=1825
```

### 4. Changelog Update

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Document Management: New endpoints for uploading, listing, and verifying borrower documents.
- Document Requirements: Tracking system to ensure mandatory documents (Identity, Income) are collected per application.
- Encryption: AES-256 encryption at rest for sensitive document types (e.g., proof_of_sin).

### Changed
- Updated application schema to support document linking.

### Fixed
- N/A
```