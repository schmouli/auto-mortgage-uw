# Document Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Document Management Module Design

**Design Location**: `docs/design/document-management.md`
**Module Path**: `mortgage_underwriting/modules/document_management/`

---

## 1. Endpoints

### `GET /api/v1/applications/{application_id}/documents/checklist`
**Authentication**: Authenticated user (applicant, broker, or underwriter)

**Response Schema**:
```json
{
  "application_id": "uuid",
  "checklist_items": [
    {
      "document_type": "government_id",
      "category": "IDENTITY",
      "is_required": true,
      "is_received": false,
      "due_date": "2024-03-15T00:00:00Z",
      "status": "overdue",
      "received_documents": []
    },
    {
      "document_type": "t4_slip",
      "category": "INCOME",
      "is_required": true,
      "is_received": true,
      "due_date": null,
      "status": "satisfied",
      "received_documents": [
        {
          "id": "uuid",
          "file_name": "t4_2023.pdf",
          "status": "accepted",
          "is_verified": true,
          "uploaded_at": "2024-01-20T14:30:00Z"
        }
      ]
    }
  ],
  "overall_status": "incomplete",
  "missing_required_count": 2
}
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `APPLICATION_001` | Application not found or user lacks access |
| 403 | `AUTH_003` | User does not have permission to view this application |

---

### `POST /api/v1/applications/{application_id}/documents/upload`
**Authentication**: Authenticated user (applicant or broker)

**Request**: `multipart/form-data`
- `file`: binary (required, max 10MB)
- `document_type`: string enum (required)
- `notes`: string optional (max 500 chars)

**Response Schema** (201 Created):
```json
{
  "id": "uuid",
  "application_id": "uuid",
  "document_type": "bank_statement",
  "file_name": "bank_statement_jan_2024.pdf",
  "file_size": 2048576,
  "mime_type": "application/pdf",
  "status": "pending",
  "is_verified": false,
  "uploaded_at": "2024-01-20T14:30:00Z",
  "download_url": "/api/v1/applications/{app_id}/documents/{doc_id}/download"
}
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 422 | `DOCUMENT_002` | Invalid document_type or MIME type (not in allowlist) |
| 413 | `DOCUMENT_004` | File size exceeds 10MB limit |
| 404 | `APPLICATION_001` | Application not found or not in editable state |
| 409 | `DOCUMENT_003` | Document type already satisfied (if duplicate not allowed) |

---

### `GET /api/v1/applications/{application_id}/documents`
**Authentication**: Authenticated user

**Query Parameters**:
- `status`: optional filter (pending/accepted/rejected)
- `category`: optional filter (IDENTITY/INCOME/PROPERTY/BANKING/DOWN_PAYMENT/OTHER)

**Response Schema**:
```json
{
  "application_id": "uuid",
  "documents": [
    {
      "id": "uuid",
      "document_type": "government_id",
      "file_name": "drivers_license.pdf",
      "status": "accepted",
      "is_verified": true,
      "file_size": 1048576,
      "mime_type": "application/pdf",
      "uploaded_at": "2024-01-20T14:30:00Z",
      "download_url": "/api/v1/applications/{app_id}/documents/{doc_id}/download"
    }
  ],
  "total_count": 1
}
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `APPLICATION_001` | Application not found |

---

### `GET /api/v1/applications/{application_id}/documents/{document_id}/download`
**Authentication**: Authenticated user

**Response**: `application/octet-stream` with `Content-Disposition: attachment; filename="sanitized_filename.pdf"`

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `DOCUMENT_001` | Document not found or user lacks access |
| 403 | `AUTH_003` | User does not have permission to download this document |

---

### `PUT /api/v1/applications/{application_id}/documents/{document_id}/verify`
**Authentication**: Underwriter or Admin role only

**Request Schema**:
```json
{
  "verification_notes": "string optional max 1000 chars"
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "status": "accepted",
  "is_verified": true,
  "verified_by": "user_uuid",
  "verified_at": "2024-01-20T15:45:00Z",
  "verification_notes": "Government ID matches application details"
}
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `DOCUMENT_001` | Document not found |
| 409 | `DOCUMENT_003` | Document already rejected or application not in underwriting state |
| 403 | `AUTH_002` | Insufficient privileges (requires underwriter role) |

---

### `PUT /api/v1/applications/{application_id}/documents/{document_id}/reject`
**Authentication**: Underwriter or Admin role only

**Request Schema**:
```json
{
  "rejection_reason": "string required min 10 max 1000 chars",
  "request_resubmission": true
}
```

**Response Schema**:
```json
{
  "id": "uuid",
  "status": "rejected",
  "is_verified": false,
  "rejection_reason": "Bank statement does not show 90-day history",
  "rejection_at": "2024-01-20T15:45:00Z",
  "rejected_by": "user_uuid",
  "request_resubmission": true
}
```

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 422 | `DOCUMENT_002` | rejection_reason missing or too short |
| 409 | `DOCUMENT_003` | Document already verified (must unverify first) |

---

### `DELETE /api/v1/applications/{application_id}/documents/{document_id}`
**Authentication**: Owner (uploader) or Admin role

**Response**: 204 No Content

**Error Responses**:
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `DOCUMENT_001` | Document not found |
| 403 | `AUTH_003` | Not owner and not admin |
| 409 | `DOCUMENT_003` | Cannot delete verified document (business rule) |

---

## 2. Models & Database

### `documents` Table
```python
class Document(Base):
    __tablename__ = "documents"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # Enum values
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)  # Sanitized client-side name
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)  # Encrypted storage path
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # Bytes
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # pending, accepted, rejected
    rejection_reason: Mapped[str] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    verified_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Audit fields (mandatory)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    
    # Relationships
    application: Mapped["Application"] = relationship(back_populates="documents")
    uploader: Mapped["User"] = relationship(foreign_keys=[uploaded_by])
    verifier: Mapped["User"] = relationship(foreign_keys=[verified_by])
    
    __table_args__ = (
        Index('idx_documents_app_type_status', 'application_id', 'document_type', 'status'),
        CheckConstraint("file_size <= 10485760", name='chk_file_size_limit'),
        CheckConstraint("status IN ('pending', 'accepted', 'rejected')", name='chk_document_status'),
    )
```

### `document_requirements` Table
```python
class DocumentRequirement(Base):
    __tablename__ = "document_requirements"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_received: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Audit fields (mandatory)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    
    # Relationships
    application: Mapped["Application"] = relationship(back_populates="document_requirements")
    
    __table_args__ = (
        Index('idx_doc_req_app_received', 'application_id', 'is_required', 'is_received'),
        UniqueConstraint('application_id', 'document_type', name='uq_app_document_type'),
    )
```

### Indexes
- `idx_documents_app_type_status`: For checklist queries and document type status checks
- `idx_documents_uploaded_by`: For user activity audit trails
- `idx_doc_req_app_received`: For finding missing required documents
- `idx_documents_verified`: For underwriter verification queue

---

## 3. Business Logic

### Document Upload Flow
1. **Validation Layer**:
   - MIME type check: `application/pdf`, `image/jpeg`, `image/png`, `image/heic`
   - File size: ≤ 10MB (10,485,760 bytes)
   - Filename sanitization: `re.sub(r'[^a-zA-Z0-9._-]', '_', filename)`
   - Virus scan placeholder: Calculate SHA256 hash and log: `{"event": "document_uploaded", "file_hash": "abc123...", "application_id": "..."}`

2. **HEIC Conversion**:
   - If `mime_type == 'image/heic'`, use `pillow-heif` library to convert to PDF
   - Store converted file, update `mime_type` to `application/pdf` and `file_size` to new size

3. **Storage Path Generation**:
   - Path template: `/uploads/{application_id}/{document_type}/{timestamp}_{sanitized_filename}`
   - Encrypt full path using `common/security.encrypt_pii()` before storing in `file_path` column
   - Store on local disk (phase 1) or S3 (phase 2) based on config

4. **Document Requirement Sync**:
   - On upload, check `document_requirements` for same `application_id` + `document_type`
   - If exists, set `is_received = True`
   - If not exists and type is known, auto-create requirement entry

### Verification State Machine
```
pending → accepted → verified
    ↓          ↓
  rejected ← unverify action
```

**Transitions**:
- `pending → accepted`: Underwriter approves document quality
- `accepted → verified`: Underwriter confirms content matches application data
- `accepted → rejected`: Underworker finds issues
- `verified → accepted`: Underwriter removes verification flag for re-review

### Document Requirement Generation Algorithm
**Input**: `Application` object with `loan_amount`, `property_value`, `employment_type`, `down_payment_source`

**Logic**:
```python
def generate_requirements(application):
    requirements = []
    ltv = application.loan_amount / application.property_value
    
    # Identity (always required)
    requirements.extend([
        ("government_id", True, None),
        ("proof_of_sin", True, None),
    ])
    
    # Income (based on employment)
    if application.employment_type == "salaried":
        requirements.extend([
            ("t4_slip", True, None),
            ("pay_stub", True, None),
            ("employment_letter", True, None),
        ])
    elif application.employment_type == "self_employed":
        requirements.extend([
            ("t1_general", True, None),
            ("financial_statements", True, None),
        ])
    
    # Property
    requirements.extend([
        ("purchase_agreement", True, None),
        ("property_tax_bill", True, None),
    ])
    
    # CMHC Insurance docs if LTV > 80%
    if ltv > Decimal('0.80'):
        requirements.append(("existing_mortgage_statement", True, None))
    
    # Down payment source-specific
    if application.down_payment_source == "gift":
        requirements.append(("gift_letter", True, None))
    
    return requirements
```

---

## 4. Migrations

### New Tables
```sql
-- Create documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    document_type VARCHAR(50) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER NOT NULL CHECK (file_size <= 10485760),
    mime_type VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
    rejection_reason TEXT,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    verified_by UUID REFERENCES users(id),
    verified_at TIMESTAMPTZ,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_documents_application_id ON documents(application_id);
CREATE INDEX idx_documents_document_type ON documents(document_type);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_app_type_status ON documents(application_id, document_type, status);

-- Create document_requirements table
CREATE TABLE document_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT true,
    is_received BOOLEAN NOT NULL DEFAULT false,
    due_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(application_id, document_type)
);

CREATE INDEX idx_doc_req_application_id ON document_requirements(application_id);
CREATE INDEX idx_doc_req_received ON document_requirements(is_required, is_received);

-- Add audit log trigger (FINTRAC compliance)
CREATE TRIGGER trg_documents_audit
    AFTER INSERT OR UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION audit.log_document_action();
```

### Data Migration
- Seed `document_requirements` for all existing applications in `submitted` or later status
- Backfill `uploaded_at` from `created_at` for existing documents if any

---

## 5. Security & Compliance

### PIPEDA
- **Encryption at Rest**: `file_path` column encrypted via `encrypt_pii()` before storage
- **Data Minimization**: Only store document metadata; never log file contents, SIN, or DOB extracted from documents
- **PII Handling**: Document processing logs include only `document_id`, `application_id`, `file_hash` - no personal data
- **Retention**: Document files retained for 5 years post-application closure; soft-delete only with `deleted_at` flag

### FINTRAC
- **Audit Trail**: Every document action logged to immutable `audit_logs` table:
  ```json
  {
    "event": "document_verified",
    "document_id": "uuid",
    "application_id": "uuid",
    "user_id": "uuid",
    "timestamp": "2024-01-20T15:45:00Z",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0..."
  }
  ```
- **Transaction Flagging**: `bank_statement` documents auto-flagged if `file_size` > threshold or parsed content shows transactions > CAD $10,000 (future OCR integration)
- **5-Year Retention**: All document records and files kept for 5 years; stored in S3 Glacier after application closure

### OSFI B-20
- **Verification Requirement**: `income` category documents MUST be `is_verified=True` before GDS/TDS calculation
- **Stress Test Audit**: When GDS/TDS calculated, system queries `documents` table to ensure required income docs are verified; logs verification status
- **Hard Stop**: If `income` docs not verified, return `UNDERWRITING_003` error: "Income documents must be verified before ratio calculation"

### Authentication & Authorization
| Endpoint | Applicant | Broker | Underwriter | Admin |
|----------|-----------|--------|-------------|-------|
| `GET checklist` | ✓ Own apps | ✓ Own apps | ✓ All apps | ✓ All apps |
| `POST upload` | ✓ Own apps | ✓ Own apps | ✗ | ✗ |
| `GET list` | ✓ Own apps | ✓ Own apps | ✓ All apps | ✓ All apps |
| `GET download` | ✓ Own apps | ✓ Own apps | ✓ All apps | ✓ All apps |
| `PUT verify` | ✗ | ✗ | ✓ | ✓ |
| `PUT reject` | ✗ | ✗ | ✓ | ✓ |
| `DELETE` | ✓ Own upload | ✓ Own upload | ✗ | ✓ |

---

## 6. Error Codes & HTTP Responses

```python
# exceptions.py
class DocumentNotFoundError(AppException):
    """Raised when document does not exist or user lacks access"""
    status_code = 404
    error_code = "DOCUMENT_001"
    message_pattern = "Document {document_id} not found"

class DocumentValidationError(AppException):
    """Raised for MIME type, size, or filename validation failures"""
    status_code = 422
    error_code = "DOCUMENT_002"
    message_pattern = "{field}: {reason}"

class DocumentBusinessRuleError(AppException):
    """Raised for state transition violations"""
    status_code = 409
    error_code = "DOCUMENT_003"
    message_pattern = "Document rule violated: {detail}"

class FileTooLargeError(AppException):
    """Specific for 10MB limit breach"""
    status_code = 413
    error_code = "DOCUMENT_004"
    message_pattern = "File size {size} exceeds 10MB limit"

class InvalidMimeTypeError(AppException):
    """Specific for MIME type validation"""
    status_code = 422
    error_code = "DOCUMENT_005"
    message_pattern = "MIME type {mime} not allowed. Accepted: {allowed}"

class VirusScanError(AppException):
    """Placeholder for future ClamAV integration"""
    status_code = 422
    error_code = "DOCUMENT_006"
    message_pattern = "Virus scan failed for file. Upload blocked."
```

### Error Response Format
```json
{
  "detail": "Document {document_id} not found",
  "error_code": "DOCUMENT_001",
  "timestamp": "2024-01-20T15:45:00Z",
  "correlation_id": "req_1234567890",
  "path": "/api/v1/applications/123/documents/456"
}
```

---

## Implementation Notes

### HEIC Conversion
- **Library**: `pillow-heif` (PyPI) with `Pillow` backend
- **Implementation**: In `services.DocumentService.process_upload()`:
  ```python
  if mime_type == "image/heic":
      heif_file = pillow_heif.open_heif(file_bytes)
      pdf_bytes = heif_file.convert_to_pdf()
      # Update file_size, mime_type, store converted bytes
  ```

### Virus Scanning (Future)
- **Integration**: ClamAV via `clamd` Python client
- **Async Processing**: Upload saves file to temp, queues scan task to Celery
- **Status**: Add `scan_status` column (pending/clean/infected) if implementing pre-storage scan

### OCR Requirements (Future)
- **Library**: `pypdf` + `pytesseract` for text extraction
- **Validation**: Extract income figures from T4/pay stubs for cross-validation with application data
- **PIPEDA Risk**: OCR output must be encrypted and never logged

### S3 Integration Path
- **Phase 1**: Local disk storage with encrypted paths
- **Phase 2**: Configurable storage backend via `common/storage.py` abstraction
- **S3 Structure**: `s3://{bucket}/applications/{application_id}/{document_type}/{uuid}_{filename}`
- **Presigned URLs**: For download endpoint to avoid proxying large files

### Document Retention Policy
- **Active Applications**: Keep all documents until 90 days post-closing
- **Rejected Applications**: Move to Glacier after 30 days, delete after 5 years
- **Closed Applications**: Move to Glacier after 1 year, delete after 5 years
- **Legal Hold**: If fraud investigation, set `retention_hold = True` to prevent deletion