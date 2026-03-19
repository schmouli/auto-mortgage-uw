# Document Management API

## POST /api/v1/documents

Upload a new document and link it to a mortgage application.

**Request:**
```json
{
  "application_id": 123,
  "document_type": "pay_stub",
  "file_name": "january_2024_paystub.pdf",
  "file_data": "<base64_encoded_file_content>",
  "mime_type": "application/pdf"
}
```

**Response (201):**
```json
{
  "id": 456,
  "application_id": 123,
  "uploaded_by": 1,
  "document_type": "pay_stub",
  "file_name": "january_2024_paystub.pdf",
  "file_path": "/secure/storage/app_123/doc_456.pdf",
  "file_size": 102400,
  "mime_type": "application/pdf",
  "status": "pending",
  "is_verified": false,
  "uploaded_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- 400: Invalid file type or size exceeds limit
- 404: Application not found
- 422: Validation error (e.g., invalid `document_type` enum)

---

## GET /api/v1/documents

Retrieve a list of documents, optionally filtered by application ID.

**Query Parameters:**
- `application_id` (int, optional): Filter documents for a specific application.
- `status` (str, optional): Filter by status (e.g., "pending", "accepted").

**Response (200):**
```json
[
  {
    "id": 456,
    "application_id": 123,
    "document_type": "pay_stub",
    "file_name": "january_2024_paystub.pdf",
    "status": "pending",
    "uploaded_at": "2026-03-02T14:30:00Z"
  }
]
```

**Errors:**
- 401: Not authenticated
- 403: Forbidden (accessing documents from another application)

---

## PATCH /api/v1/documents/{id}

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
  "id": 456,
  "status": "accepted",
  "is_verified": true,
  "verified_by": 2,
  "verified_at": "2026-03-02T15:00:00Z",
  "rejection_reason": null
}
```

**Errors:**
- 400: Cannot verify a document that is already verified
- 404: Document not found
- 422: Validation error (e.g., missing `rejection_reason` when status is "rejected")

---

## GET /api/v1/document-requirements

Check the document checklist for a specific application to see what is required and what has been received.

**Query Parameters:**
- `application_id` (int, required): The application ID to check requirements for.

**Response (200):**
```json
[
  {
    "id": 1,
    "application_id": 123,
    "document_type": "government_id",
    "is_required": true,
    "is_received": true,
    "due_date": "2026-03-15T00:00:00Z"
  },
  {
    "id": 2,
    "application_id": 123,
    "document_type": "t1_general",
    "is_required": true,
    "is_received": false,
    "due_date": "2026-03-15T00:00:00Z"
  }
]
```

**Errors:**
- 401: Not authenticated
- 404: Application not found

---

# Document Management Module

## Overview
The Document Management module handles the secure storage, tracking, and verification of borrower documentation required for mortgage underwriting. It ensures that all necessary files (Identity, Income, etc.) are collected, immutable audit trails are maintained (FINTRAC), and sensitive data is handled securely (PIPEDA).

## Key Functions

### 1. Secure Upload & Storage
- **Function**: `services.upload_document`
- **Description**: Accepts file uploads, validates MIME types, saves files to the configured secure storage path, and creates a database record.
- **Compliance**: 
  - Files containing PII (like `proof_of_sin`) are encrypted at rest (AES-256).
  - Audit fields (`uploaded_by`, `uploaded_at`) are automatically populated.

### 2. Requirement Checklist
- **Function**: `services.get_requirements`
- **Description**: Dynamically generates a list of required documents based on the application type and compares it against received documents.
- **Logic**: Updates `is_received` flag in `document_requirements` when matching documents are uploaded.

### 3. Verification Workflow
- **Function**: `services.verify_document`
- **Description**: Allows underwriters to mark documents as `accepted` or `rejected`.
- **Audit**: Tracks `verified_by` (User ID) and `verified_at` timestamp. If rejected, a reason must be provided.

## Usage Examples

### Uploading a Government ID
```python
# Pseudocode for service usage
await document_service.upload_document(
    application_id=101,
    uploaded_by=user_id,
    document_type="government_id",
    file_data=bytes_content,
    mime_type="image/jpeg"
)
# Result: File encrypted and stored. Record created with status='pending'.
```

### Verifying Income Documents
```python
# Pseudocode for underwriting action
await document_service.verify_document(
    document_id=456,
    verifier_id=underwriter_id,
    status="accepted"
)
# Result: Document status updated. 'is_received' flag in requirements updated to True.
```

## Security Notes
- **PIPEDA Compliance**: Documents classified as `proof_of_sin` trigger encryption routines. File paths are returned in API responses, but file contents are never logged.
- **FINTRAC Compliance**: Document records are never deleted (soft delete only if implemented, but architecture suggests immutable history). Verification logs are retained for 5 years.

---

# Configuration Notes

## Environment Variables

Update `.env.example` with the following variables for the Document Management module:

```bash
# Document Management Configuration
# Path where encrypted files are stored (ensure volume permissions are secure)
DOCUMENT_STORAGE_PATH=/var/lib/mortgage_docs

# Maximum file upload size in Megabytes
MAX_UPLOAD_SIZE_MB=10

# Comma-separated list of allowed MIME types (e.g., application/pdf, image/jpeg)
ALLOWED_MIME_TYPES=application/pdf,image/jpeg,image/png

# Encryption key for AES-256 at-rest encryption (Must be 32 bytes/url-safe base64 encoded)
# WARNING: Rotate this key carefully as it requires re-encrypting existing files.
DOCUMENT_ENCRYPTION_KEY=
```