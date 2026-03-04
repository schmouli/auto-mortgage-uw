# Design: Document Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Document Management Module Design Plan

**Module Identifier:** `DOCUMENT`  
**Feature Slug:** `document-management`  
**Design Doc:** `docs/design/document-management.md`

---

## 1. Endpoints

### `GET /api/v1/applications/{application_id}/documents/checklist`
**Authentication:** Authenticated user (applicant, broker, or underwriter with application access)  
**Description:** Returns the document requirements checklist for a mortgage application with receipt and verification status.

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "checklist": [
    {
      "document_type": "government_id",
      "category": "IDENTITY",
      "is_required": true,
      "is_received": true,
      "received_document_id": "uuid",
      "is_verified": true,
      "due_date": "2024-01-15T23:59:59Z",
      "status": "verified"
    }
  ],
  "summary": {
    "total_required": 12,
    "received": 10,
    "verified": 8,
    "overdue": 2
  }
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 404 | `APPLICATION_001` | "Application {id} not found" |
| 403 | `DOCUMENT_004` | "Access denied to application documents" |
| 422 | `DOCUMENT_002` | "application_id: invalid UUID format" |

---

### `POST /api/v1/applications/{application_id}/documents/upload`
**Authentication:** Authenticated user (applicant or broker with write access)  
**Content-Type:** `multipart/form-data`  
**Description:** Uploads a single document file after validation and virus scan placeholder.

**Request Body:**
- `file`: Binary file data (max 10MB)
- `document_type`: string (enum from document_types list)
- `notes`: optional string (max 500 chars)

**Response Schema (201 Created):**
```json
{
  "document_id": "uuid",
  "application_id": "uuid",
  "document_type": "bank_statement",
  "file_name": "bank_statement_jan_2024.pdf",
  "file_size": 2048576,
  "mime_type": "application/pdf",
  "status": "pending",
  "is_verified": false,
  "uploaded_at": "2024-01-10T14:30:00Z",
  "uploaded_by": "uuid"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 404 | `APPLICATION_001` | "Application {id} not found" |
| 403 | `DOCUMENT_004` | "Access denied to upload documents" |
| 413 | `DOCUMENT_002` | "File size exceeds 10MB limit" |
| 415 | `DOCUMENT_002` | "Unsupported MIME type: {type}" |
| 422 | `DOCUMENT_002` | "document_type: invalid enum value" |
| 422 | `DOCUMENT_002` | "File name contains invalid characters" |
| 409 | `DOCUMENT_003` | "Document already uploaded for this type" |

---

### `GET /api/v1/applications/{application_id}/documents`
**Authentication:** Authenticated user with application access  
**Description:** Lists all uploaded documents for an application (file paths excluded).

**Query Parameters:**
- `status`: optional filter (pending/accepted/rejected)
- `document_type`: optional filter

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "documents": [
    {
      "document_id": "uuid",
      "document_type": "t4_slip",
      "file_name": "t4_2023.pdf",
      "file_size": 1048576,
      "mime_type": "application/pdf",
      "status": "accepted",
      "is_verified": true,
      "verified_at": "2024-01-11T09:00:00Z",
      "uploaded_at": "2024-01-10T14:30:00Z",
      "rejection_reason": null
    }
  ],
  "total_count": 5
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 404 | `APPLICATION_001` | "Application {id} not found" |
| 403 | `DOCUMENT_004` | "Access denied to application documents" |
| 422 | `DOCUMENT_002` | "status: invalid filter value" |

---

### `GET /api/v1/applications/{application_id}/documents/{document_id}/download`
**Authentication:** Authenticated user with application access  
**Description:** Securely streams the document file content.

**Response:** `application/octet-stream` with `Content-Disposition: attachment; filename="{sanitized_name}"`

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 404 | `DOCUMENT_001` | "Document {doc_id} not found" |
| 403 | `DOCUMENT_004` | "Access denied to document" |
| 410 | `DOCUMENT_001` | "Document has been archived" |
| 422 | `DOCUMENT_002` | "document_id: invalid UUID format" |

---

### `PUT /api/v1/applications/{application_id}/documents/{document_id}/verify`
**Authentication:** Underwriter or admin role only  
**Description:** Marks a document as verified and updates requirement status.

**Request Body:** Empty (audit fields auto-populated)

**Response Schema (200 OK):**
```json
{
  "document_id": "uuid",
  "is_verified": true,
  "verified_by": "uuid",
  "verified_at": "2024-01-11T09:00:00Z",
  "status": "accepted"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 404 | `DOCUMENT_001` | "Document {doc_id} not found" |
| 403 | `DOCUMENT_004` | "Underwriter role required" |
| 409 | `DOCUMENT_003` | "Document already verified" |
| 409 | `DOCUMENT_003` | "Cannot verify rejected document" |

---

### `PUT /api/v1/applications/{application_id}/documents/{doc_id}/reject`
**Authentication:** Underwriter or admin role only  
**Description:** Rejects a document with a mandatory reason.

**Request Body:**
```json
{
  "rejection_reason": "Bank statement is incomplete - missing last 30 days"
}
```

**Response Schema (200 OK):**
```json
{
  "document_id": "uuid",
  "status": "rejected",
  "rejection_reason": "Bank statement is incomplete - missing last 30 days",
  "is_verified": false
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 404 | `DOCUMENT_001` | "Document {doc_id} not found" |
| 403 | `DOCUMENT_004` | "Underwriter role required" |
| 409 | `DOCUMENT_003` | "Cannot reject verified document" |
| 422 | `DOCUMENT_002` | "rejection_reason: minimum 10 characters required" |

---

### `DELETE /api/v1/applications/{application_id}/documents/{document_id}`
**Authentication:** Underwriter or admin role only (FINTRAC retention compliance)  
**Description:** Soft-deletes a document (sets `is_deleted` flag for 5-year retention).

**Response:** `204 No Content`

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 404 | `DOCUMENT_001` | "Document {doc_id} not found" |
| 403 | `DOCUMENT_004` | "Admin role required for deletion" |
| 409 | `DOCUMENT_003` | "Cannot delete verified document" |

---

## 2. Models & Database

### `documents` Table
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE RESTRICT,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    document_type VARCHAR(50) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL, -- ENCRYPTED at rest (AES-256)
    file_size INTEGER NOT NULL CHECK (file_size <= 10485760), -- 10MB max
    mime_type VARCHAR(100) NOT NULL CHECK (mime_type IN (
        'application/pdf', 'image/jpeg', 'image/png', 'image/heic'
    )),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' 
        CHECK (status IN ('pending', 'accepted', 'rejected')),
    rejection_reason TEXT,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    verified_by UUID REFERENCES users(id),
    verified_at TIMESTAMP,
    file_hash VARCHAR(64), -- SHA256 for virus scan tracking
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    deleted_at TIMESTAMP,
    uploaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Audit logging compliance
    created_by VARCHAR(100) NOT NULL, -- JWT subject claim
    last_modified_by VARCHAR(100) -- JWT subject claim
    
    -- Indexes
    CREATE INDEX idx_documents_application_id ON documents(application_id);
    CREATE INDEX idx_documents_app_type ON documents(application_id, document_type);
    CREATE INDEX idx_documents_status ON documents(status);
    CREATE INDEX idx_documents_is_verified ON documents(is_verified);
    CREATE INDEX idx_documents_uploaded_by ON documents(uploaded_by);
);
```

### `document_requirements` Table
```sql
CREATE TABLE document_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT true,
    is_received BOOLEAN NOT NULL DEFAULT false,
    due_date TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Composite unique constraint
    UNIQUE(application_id, document_type),
    
    -- Indexes
    CREATE INDEX idx_docreq_application_id ON document_requirements(application_id);
    CREATE INDEX idx_docreq_app_type ON document_requirements(application_id, document_type);
    CREATE INDEX idx_docreq_due_date ON document_requirements(due_date) 
        WHERE is_required = true AND is_received = false;
);
```

### Document Type Enum (Python)
```python
class DocumentType(str, Enum):
    # IDENTITY
    GOVERNMENT_ID = "government_id"
    PROOF_OF_SIN = "proof_of_sin"
    # INCOME
    T4_SLIP = "t4_slip"
    NOA = "noa"
    PAY_STUB = "pay_stub"
    EMPLOYMENT_LETTER = "employment_letter"
    T1_GENERAL = "t1_general"
    FINANCIAL_STATEMENTS = "financial_statements"
    RENTAL_INCOME_STATEMENT = "rental_income_statement"
    # PROPERTY
    PURCHASE_AGREEMENT = "purchase_agreement"
    MLS_LISTING = "mls_listing"
    PROPERTY_TAX_BILL = "property_tax_bill"
    CONDO_STATUS_CERT = "condo_status_cert"
    # BANKING
    BANK_STATEMENT = "bank_statement"
    VOID_CHEQUE = "void_cheque"
    # DOWN_PAYMENT
    GIFT_LETTER = "gift_letter"
    RRSP_WITHDRAWAL_CONFIRMATION = "rrsp_withdrawal_confirmation"
    SALE_PROCEEDS_CONFIRMATION = "sale_proceeds_confirmation"
    # OTHER
    EXISTING_MORTGAGE_STATEMENT = "existing_mortgage_statement"
    DIVORCE_DECREE = "divorce_decree"
    BANKRUPTCY_DISCHARGE = "bankruptcy_discharge"
```

---

## 3. Business Logic

### Upload Document Workflow
1. **Authorization Check**: Verify user has `write:documents` scope for the application
2. **Application State Validation**: Only allow uploads for applications in `draft`, `submitted`, or `underwriting` status
3. **File Size Validation**: Reject if `file.size > 10_485_760` bytes (10MB)
4. **MIME Type Detection**: 
   - Inspect magic bytes, not just extension
   - Accept: `application/pdf`, `image/jpeg`, `image/png`, `image/heic`
5. **Filename Sanitization**: 
   - Strip all characters except `a-zA-Z0-9_.-`
   - Replace spaces with underscores
   - Limit length to 100 characters
   - Prepend UUID to prevent collisions: `{uuid}_{sanitized_name}`
6. **HEIC Conversion**:
   - Use `Pillow` with `pyheif` plugin
   - Convert to PDF, maintain original resolution
   - Update `mime_type` to `application/pdf` post-conversion
   - Log conversion event with correlation_id
7. **File Hashing**: Compute SHA256 hash for virus scan audit trail
8. **Path Generation**: `/uploads/{application_id}/{document_type}/{uuid}_{filename}`
9. **Storage**: Write to local filesystem (phase 1) or S3 (future)
10. **Database Insert**: Encrypt `file_path` using `encrypt_pii()` from `common.security`
11. **Audit Log**: `structlog` entry with `action="document_uploaded"`, `file_hash`, `document_type`, **no PII**
12. **Async Task**: Queue virus scan placeholder task (logs hash for future ClamAV integration)

### Verification Workflow
1. **Role Check**: Require `underwriter` role or `document:verify` permission
2. **State Check**: Document must be `pending` or `accepted`, not `rejected` or already verified
3. **Update Document**: Set `is_verified=True`, `verified_by=current_user.id`, `verified_at=now()`, `status='accepted'`
4. **Update Requirement**: Set `document_requirements.is_received=True` for matching `(application_id, document_type)`
5. **Audit Log**: `action="document_verified"` with `document_id`, `verified_by`
6. **Trigger**: Emit `DocumentVerified` event for underwriting workflow engine

### Rejection Workflow
1. **Role Check**: Require `underwriter` role
2. **Validation**: `rejection_reason` must be 10-500 characters
3. **State Check**: Cannot reject verified documents (must unverify first)
4. **Update Document**: Set `status='rejected'`, `rejection_reason`, `is_verified=False`
5. **Update Requirement**: Set `document_requirements.is_received=False`
6. **Audit Log**: `action="document_rejected"` with reason hash (not full text)
7. **Notification**: Queue email to applicant (via notification module)

### Deletion Workflow (Soft Delete)
1. **Role Check**: Require `admin` role (FINTRAC 5-year retention)
2. **State Check**: Cannot delete verified documents; must unverify first
3. **Soft Delete**: Set `is_deleted=True`, `deleted_at=now()`
4. **Audit Log**: `action="document_deleted"` with `deleted_by`
5. **File Retention**: Keep file on disk for 5 years (compliance)

### Checklist Generation Logic
```python
def generate_checklist(application_id: UUID) -> List[DocumentRequirementStatus]:
    requirements = db.query(DocumentRequirement).filter(
        application_id=application_id
    ).all()
    
    documents = db.query(Document).filter(
        application_id=application_id,
        is_deleted=False
    ).all()
    
    doc_map = {(d.document_type, d.is_verified): d for d in documents}
    
    result = []
    for req in requirements:
        doc = doc_map.get((req.document_type, True)) or doc_map.get((req.document_type, False))
        result.append(DocumentRequirementStatus(
            document_type=req.document_type,
            is_required=req.is_required,
            is_received=req.is_received,
            received_document_id=doc.id if doc else None,
            is_verified=doc.is_verified if doc else False,
            due_date=req.due_date,
            status=_calculate_status(req, doc)
        ))
    return result
```

---

## 4. Migrations

### Alembic Revision: `create_document_management_tables`

**New Tables:**
```python
def upgrade():
    # documents table
    op.create_table('documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('uploaded_by', sa.UUID(), nullable=False),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('verified_by', sa.UUID(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('last_modified_by', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id']),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # document_requirements table
    op.create_table('document_requirements',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False),
        sa.Column('is_received', sa.Boolean(), nullable=False),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('application_id', 'document_type')
    )
    
    # Indexes
    op.create_index('idx_documents_application_id', 'documents', ['application_id'])
    op.create_index('idx_documents_app_type', 'documents', ['application_id', 'document_type'])
    op.create_index('idx_documents_status', 'documents', ['status'])
    op.create_index('idx_documents_is_verified', 'documents', ['is_verified'])
    op.create_index('idx_docreq_application_id', 'document_requirements', ['application_id'])
    op.create_index('idx_docreq_app_type', 'document_requirements', ['application_id', 'document_type'])
    op.create_index('idx_docreq_due_date', 'document_requirements', ['due_date'],
                    postgresql_where=sa.text("is_required = true AND is_received = false"))
```

**Data Migration Needs:** None (new module)

---

## 5. Security & Compliance

### FINTRAC Compliance (Mandatory)
- **Immutable Audit Trail**: All `documents` table records are **never hard-deleted**. `is_deleted` flag used for soft deletion.
- **5-Year Retention**: Soft-deleted documents retained for 5 years. Archive policy: move to S3 Glacier after 1 year of deletion.
- **Transaction Logging**: All document actions logged with `correlation_id`, `user_id`, `timestamp`, `action_type`. **Never log file contents or PII**.
- **Large Transaction Flag**: Documents for applications with loan_amount > CAD $10,000 must be flagged as `high_value=True` in audit log (derived from applications table).

### PIPEDA Compliance (Mandatory)
- **Encryption at Rest**: `file_path` column encrypted using AES-256 via `encrypt_pii()` function. File contents stored on encrypted volume (dm-crypt/LUKS).
- **Data Minimization**: Only document metadata stored; file contents never processed for PII extraction unless explicitly required for underwriting.
- **Path Exposure**: Internal file paths **never** exposed in API responses. Download endpoint streams content directly without redirect.
- **Secure Transmission**: All file uploads/downloads over TLS 1.3. File download endpoint validates user authorization per request.

### OSFI B-20 (Auditable)
- **Audit Logging**: Every document state change (upload, verify, reject, delete) logged with complete context for underwriting decision traceability.
- **GDS/TDS Integration**: Document verification status feeds into underwriting calculator; missing required docs blocks approval.

### Authentication & Authorization
| Endpoint | Required Scope/Role |
|----------|---------------------|
| `GET /checklist` | `read:documents` (application owner or underwriter) |
| `POST /upload` | `write:documents` (applicant/broker for own applications) |
| `GET /list` | `read:documents` (application owner or underwriter) |
| `GET /download` | `read:documents` (application owner or underwriter) |
| `PUT /verify` | `role:underwriter` or `permission:document_verify` |
| `PUT /reject` | `role:underwriter` or `permission:document_reject` |
| `DELETE /{id}` | `role:admin` (FINTRAC retention compliance) |

### File Security Implementation
- **Storage Path**: `/uploads/{application_id}/{document_type}/` outside web root
- **Filename Obfuscation**: `{uuid}_{sanitized_name}` prevents enumeration
- **Permissions**: Files created with `640` (owner: app user, group: app group)
- **Virus Scan**: Async Celery task computes SHA256 hash, logs to `document_scans` table (future ClamAV integration)
- **HEIC Conversion**: Server-side conversion using `Pillow[heif]` library; original HEIC **not retained** post-conversion

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy
```python
# In modules/document/exceptions.py
class DocumentException(AppException):
    """Base exception for document management module"""
    module_code = "DOCUMENT"

class DocumentNotFoundError(DocumentException):
    """Raised when document UUID does not exist or is soft-deleted"""
    http_status = 404
    error_code = "DOCUMENT_001"

class DocumentValidationError(DocumentException):
    """Raised for MIME type, size, filename, or schema validation failures"""
    http_status = 422
    error_code = "DOCUMENT_002"

class DocumentBusinessRuleError(DocumentException):
    """Raised for state transition violations (verify rejected doc, etc.)"""
    http_status = 409
    error_code = "DOCUMENT_003"

class DocumentAccessDeniedError(DocumentException):
    """Raised when user lacks permission for the operation"""
    http_status = 403
    error_code = "DOCUMENT_004"
```

### Error Response Format
All errors return consistent JSON:
```json
{
  "detail": "Document not found",
  "error_code": "DOCUMENT_001",
  "module": "document_management",
  "timestamp": "2024-01-10T15:30:00Z",
  "correlation_id": "req-1234567890"
}
```

### Edge Cases & Error Handling
- **Concurrent Uploads**: Database unique constraint on `(application_id, document_type, is_verified=True)` prevents race conditions
- **Partial Upload Failure**: If storage write fails, database transaction rolled back; client must retry
- **HEIC Conversion Failure**: Return `DOCUMENT_002` with detail "HEIC conversion failed: {error}"
- **Virus Scan Timeout**: Log warning, allow upload, mark `scan_status='pending'` for future retry
- **S3 Integration Path**: When migrating to S3, `file_path` stores `s3://bucket/key` format; download endpoint generates pre-signed URLs (TTL 60s)

---

## 7. Missing Details & Recommendations

### HEIC to PDF Conversion
**Library Selection**: `Pillow` with `pyheif` plugin (install via `uv add "Pillow[heif]" pyheif`)  
**Implementation**: Async conversion in `DocumentService.convert_heic_to_pdf()` with timeout handling  
**Quality**: Maintain 300 DPI resolution; embed metadata in PDF

### Virus Scanning Timeline
**Phase 1 (MVP)**: Log file hash only (`file_hash` column)  
**Phase 2 (Q2 2024)**: Integrate ClamAV via `celery` worker; update `scan_status` enum: `pending/clean/quarantined`  
**Phase 3 (Q3 2024)**: Implement S3 event trigger for automatic scanning on upload

### OCR Requirements
**Future Enhancement**: Use AWS Textract or Azure Form Recognizer for income document parsing  
**PIPEDA Warning**: OCR output must be encrypted; no PII logged  
**Trigger**: Only for `t4_slip`, `noa`, `pay_stub` types when `is_verified=True`

### Document Retention Policy
| Document Type | Retention Period | Archive Action |
|---------------|------------------|----------------|
| IDENTITY | 5 years | S3 Glacier after 1 year |
| INCOME | 5 years | S3 Glacier after 1 year |
| PROPERTY | 5 years | S3 Glacier after 1 year |
| BANKING | 5 years | S3 Glacier after 6 months |
| DOWN_PAYMENT | 5 years | S3 Glacier after 1 year |
| OTHER | 5 years | S3 Glacier after 1 year |

**Implementation**: Daily Celery task moves `is_deleted=True` docs older than archive threshold to S3 Glacier, updates `file_path` to glacier URI.

### S3 Integration Path
**Architecture**: 
- Phase 1: Local filesystem with encrypted volume
- Phase 2: S3 Standard with IAM role for EC2/task
- Phase 3: S3 Intelligent-Tiering with lifecycle policies

**Code Path**: `DocumentStorageService` abstraction with `LocalStorageBackend` and `S3StorageBackend` implementations. Switch via `config.DOCUMENT_STORAGE_BACKEND` setting.