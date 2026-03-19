# Document Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Document Management Module Design Plan

**File:** `docs/design/document-management.md`

---

## 1. Endpoints

### 1.1 GET /api/v1/applications/{application_id}/documents/checklist
**Purpose:** Retrieve document requirements status for a mortgage application.

**Authentication:** Authenticated user (borrower, broker, or underwriter)

**Path Parameters:**
- `application_id`: UUID - The mortgage application identifier

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "overall_status": "pending|complete|overdue",
  "requirements": [
    {
      "document_type": "government_id",
      "category": "IDENTITY",
      "is_required": true,
      "is_received": false,
      "due_date": "2024-01-15T23:59:59Z",
      "days_until_due": 5,
      "received_document_id": null,
      "received_at": null,
      "status": "pending"
    },
    {
      "document_type": "bank_statement",
      "category": "BANKING",
      "is_required": true,
      "is_received": true,
      "due_date": "2024-01-10T23:59:59Z",
      "days_until_due": 0,
      "received_document_id": "uuid",
      "received_at": "2024-01-08T14:30:00Z",
      "status": "accepted"
    }
  ],
  "missing_required_count": 3,
  "pending_verification_count": 2
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail | Trigger Condition |
|-------------|------------|--------|-------------------|
| 401 | AUTH_001 | "Authentication required" | Missing or invalid JWT token |
| 403 | AUTH_002 | "Access denied" | User lacks permission for this application |
| 404 | DOC_001 | "Application not found" | application_id does not exist |
| 422 | DOC_002 | "Invalid UUID format" | Malformed application_id |

---

### 1.2 POST /api/v1/applications/{application_id}/documents/upload
**Purpose:** Upload a single document file (multipart/form-data).

**Authentication:** Authenticated user (borrower or broker)

**Path Parameters:**
- `application_id`: UUID

**Request Body (multipart/form-data):**
- `document_type`: string (enum) - Required. One of predefined document types
- `file`: binary - Required. File content
- `description`: string - Optional. User-provided description

**Response Schema (201 Created):**
```json
{
  "document_id": "uuid",
  "application_id": "uuid",
  "document_type": "t4_slip",
  "file_name": "t4_2023.pdf",
  "file_size": 1048576,
  "mime_type": "application/pdf",
  "status": "pending",
  "is_verified": false,
  "uploaded_at": "2024-01-10T14:30:00Z",
  "uploaded_by": "uuid",
  "checksum_sha256": "a3f5c8e2...",
  "conversion_applied": null
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail | Trigger Condition |
|-------------|------------|--------|-------------------|
| 400 | DOC_003 | "Invalid document type" | document_type not in allowed enum |
| 400 | DOC_004 | "File exceeds maximum size (10MB)" | file_size > 10MB |
| 400 | DOC_005 | "Unsupported MIME type" | MIME type not in [PDF, JPEG, PNG, HEIC] |
| 400 | DOC_006 | "Virus scan failed" | File hash matches known malware pattern |
| 401 | AUTH_001 | "Authentication required" | Missing JWT token |
| 403 | AUTH_002 | "Access denied" | User not associated with application |
| 404 | DOC_001 | "Application not found" | application_id does not exist |
| 409 | DOC_007 | "Document already uploaded" | Same document_type already received |
| 413 | DOC_008 | "Payload too large" | Request body > 10MB |
| 422 | DOC_002 | "Invalid UUID format" | Malformed application_id |

**Processing Pipeline:**
1. Validate MIME type and file size
2. Sanitize filename (remove `[^a-zA-Z0-9._-]`, limit to 255 chars)
3. Generate SHA256 checksum
4. **Virus Scan Placeholder:** Log checksum for future ClamAV integration
5. Convert HEIC → PDF if needed (server-side, temporary processing)
6. Store in `/uploads/{application_id}/{document_type}/{uuid}_{sanitized_filename}`
7. Create database record with `status: pending`

---

### 1.3 GET /api/v1/applications/{application_id}/documents
**Purpose:** List all uploaded documents for an application.

**Authentication:** Authenticated user (borrower, broker, or underwriter)

**Path Parameters:**
- `application_id`: UUID

**Query Parameters:**
- `status`: string - Optional. Filter by status
- `document_type`: string - Optional. Filter by type
- `is_verified`: boolean - Optional. Filter by verification state

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "documents": [
    {
      "document_id": "uuid",
      "document_type": "government_id",
      "category": "IDENTITY",
      "file_name": "drivers_license.pdf",
      "file_size": 524288,
      "mime_type": "application/pdf",
      "status": "accepted",
      "is_verified": true,
      "verified_by": "uuid",
      "verified_at": "2024-01-11T10:00:00Z",
      "uploaded_at": "2024-01-10T14:30:00Z",
      "rejection_reason": null,
      "download_url": "/api/v1/applications/{id}/documents/{doc_id}/download"
    }
  ],
  "total_count": 1
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail | Trigger Condition |
|-------------|------------|--------|-------------------|
| 401 | AUTH_001 | "Authentication required" | Missing JWT token |
| 403 | AUTH_002 | "Access denied" | User lacks permission |
| 404 | DOC_001 | "Application not found" | application_id does not exist |
| 422 | DOC_002 | "Invalid UUID format" | Malformed application_id |

---

### 1.4 GET /api/v1/applications/{application_id}/documents/{document_id}/download
**Purpose:** Download document file content (returns binary stream).

**Authentication:** Authenticated user

**Path Parameters:**
- `application_id`: UUID
- `document_id`: UUID

**Response (200 OK):**
- `Content-Type`: application/octet-stream
- `Content-Disposition`: attachment; filename="{sanitized_filename}"
- Body: Binary file content

**Error Responses:**
| HTTP Status | Error Code | Detail | Trigger Condition |
|-------------|------------|--------|-------------------|
| 401 | AUTH_001 | "Authentication required" | Missing JWT token |
| 403 | AUTH_002 | "Access denied" | User lacks permission |
| 404 | DOC_009 | "Document not found" | document_id does not exist |
| 410 | DOC_010 | "Document expired" | Retention period exceeded (FINTRAC 5-year rule) |

**Security Note:** Internal file path is never exposed. Stream file directly from storage backend.

---

### 1.5 PUT /api/v1/applications/{application_id}/documents/{document_id}/verify
**Purpose:** Mark a document as verified (underwriter action).

**Authentication:** Authenticated underwriter with `document:verify` permission

**Path Parameters:**
- `application_id`: UUID
- `document_id`: UUID

**Request Body:**
```json
{
  "verification_notes": "Government ID matches application details"
}
```

**Response Schema (200 OK):**
```json
{
  "document_id": "uuid",
  "status": "accepted",
  "is_verified": true,
  "verified_by": "uuid",
  "verified_at": "2024-01-11T10:00:00Z",
  "verification_notes": "Government ID matches application details"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail | Trigger Condition |
|-------------|------------|--------|-------------------|
| 401 | AUTH_001 | "Authentication required" | Missing JWT token |
| 403 | AUTH_003 | "Insufficient permissions" | User lacks `document:verify` role |
| 404 | DOC_009 | "Document not found" | document_id does not exist |
| 409 | DOC_011 | "Document already verified" | is_verified already true |
| 422 | DOC_002 | "Invalid UUID format" | Malformed UUID |

**FINTRAC Compliance:** Logs identity verification event with `created_by` for audit trail.

---

### 1.6 PUT /api/v1/applications/{application_id}/documents/{document_id}/reject
**Purpose:** Reject a document with reason (underwriter action).

**Authentication:** Authenticated underwriter with `document:verify` permission

**Path Parameters:**
- `application_id`: UUID
- `document_id`: UUID

**Request Body:**
```json
{
  "rejection_reason": "Document incomplete or illegible",
  "rejection_details": "Missing signature page"
}
```

**Response Schema (200 OK):**
```json
{
  "document_id": "uuid",
  "status": "rejected",
  "is_verified": false,
  "rejection_reason": "Document incomplete or illegible",
  "rejection_details": "Missing signature page",
  "rejected_by": "uuid",
  "rejected_at": "2024-01-11T10:00:00Z"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail | Trigger Condition |
|-------------|------------|--------|-------------------|
| 400 | DOC_012 | "Rejection reason required" | rejection_reason empty or missing |
| 401 | AUTH_001 | "Authentication required" | Missing JWT token |
| 403 | AUTH_003 | "Insufficient permissions" | User lacks verification role |
| 404 | DOC_009 | "Document not found" | document_id does not exist |
| 409 | DOC_013 | "Cannot reject verified document" | Document already verified |

---

### 1.7 DELETE /api/v1/applications/{application_id}/documents/{document_id}
**Purpose:** Soft-delete a document (marks as deleted, file remains for retention).

**Authentication:** Authenticated user who uploaded the document OR underwriter

**Path Parameters:**
- `application_id`: UUID
- `document_id`: UUID

**Response Schema (204 No Content)**

**Error Responses:**
| HTTP Status | Error Code | Detail | Trigger Condition |
|-------------|------------|--------|-------------------|
| 401 | AUTH_001 | "Authentication required" | Missing JWT token |
| 403 | AUTH_002 | "Access denied" | User neither uploader nor underwriter |
| 404 | DOC_009 | "Document not found" | document_id does not exist |
| 409 | DOC_014 | "Cannot delete verified document" | Document already verified |

**FINTRAC Compliance:** Soft-delete only; file retained for 5-year regulatory period.

---

## 2. Models & Database

### 2.1 documents Table
```python
class Document(Base):
    __tablename__ = "documents"
    
    # Primary Key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # Foreign Keys
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    verified_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    
    # Document Metadata
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)  # Sanitized filename
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)  # Internal storage path
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Bytes
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Status & Verification
    status: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        default="pending",
        index=True
    )  # Enum: pending, accepted, rejected
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(default=False, index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Audit & Compliance
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=func.now(),
        onupdate=func.now()
    )
    
    # Security & Integrity
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)  # For virus scanning
    conversion_applied: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "heic_to_pdf" etc
    
    # Soft Delete (FINTRAC retention)
    is_deleted: Mapped[bool] = mapped_column(default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Relationships
    application: Mapped["Application"] = relationship(back_populates="documents")
    uploader: Mapped["User"] = relationship(foreign_keys=[uploaded_by])
    verifier: Mapped["User | None"] = relationship(foreign_keys=[verified_by])
```

**Indexes:**
- Composite: `(application_id, document_type, is_deleted)` - for checklist queries
- Composite: `(application_id, status, is_verified)` - for underwriter queues
- Composite: `(uploaded_by, uploaded_at DESC)` - for user upload history
- Single: `(checksum_sha256)` - for virus scan deduplication

---

### 2.2 document_requirements Table
```python
class DocumentRequirement(Base):
    __tablename__ = "document_requirements"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), nullable=False, index=True)
    
    # Requirement Definition
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)  # IDENTITY, INCOME, etc.
    is_required: Mapped[bool] = mapped_column(default=True, index=True)
    is_received: Mapped[bool] = mapped_column(default=False, index=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Dynamic Calculation Cache
    received_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    application: Mapped["Application"] = relationship(back_populates="document_requirements")
    received_document: Mapped["Document | None"] = relationship()
```

**Indexes:**
- Unique composite: `(application_id, document_type)` - prevents duplicate requirements
- Composite: `(application_id, is_required, is_received)` - for missing docs queries
- Composite: `(due_date, is_received)` - for overdue notifications

---

### 2.3 Document Type Enum
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

### 3.1 Document Validation Pipeline
**Synchronous Steps (on upload):**
1. **MIME Type Validation:** Check `content-type` header and file signature magic bytes
   - Allowed: `application/pdf`, `image/jpeg`, `image/png`, `image/heic`
   - Reject with `DOC_005` if unsupported

2. **File Size Validation:** 
   - Read stream until 10MB + 1 byte threshold
   - Reject with `DOC_004` if exceeded

3. **Filename Sanitization:**
   ```python
   import re
   sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', original_filename)
   sanitized = sanitized[:255]
   ```

4. **Checksum Generation:** Compute SHA256 hash for virus scanning and deduplication

5. **Virus Scan Placeholder:**
   ```python
   logger.info("file_uploaded", 
               checksum=checksum, 
               application_id=app_id, 
               doc_type=doc_type,
               audit_action="virus_scan_pending")
   # Future: Integrate ClamAV daemon via python-clamd
   ```

6. **HEIC Conversion:**
   - Use `pillow-heif` library for HEIC → JPEG conversion
   - Then use `reportlab` to wrap JPEG in PDF container
   - Set `conversion_applied = "heic_to_pdf"`
   - **WARNING:** Conversion may affect image quality; log original checksum

### 3.2 Document Requirement Engine
**Trigger:** On application creation or status change to `submitted`

**Logic:**
```python
def generate_requirements(application: Application):
    requirements = []
    
    # IDENTITY (always required)
    requirements.append(("government_id", "IDENTITY", True))
    requirements.append(("proof_of_sin", "IDENTITY", True))  # FINTRAC: Identity verification
    
    # INCOME (based on employment type)
    if application.employment_type == "salaried":
        requirements.append(("pay_stub", "INCOME", True))
        requirements.append(("t4_slip", "INCOME", True))
        requirements.append(("noa", "INCOME", True))
    elif application.employment_type == "self_employed":
        requirements.append(("t1_general", "INCOME", True))
        requirements.append(("financial_statements", "INCOME", True))
    
    # PROPERTY (if purchase)
    if application.loan_purpose == "purchase":
        requirements.append(("purchase_agreement", "PROPERTY", True))
        requirements.append(("mls_listing", "PROPERTY", False))
    
    # BANKING (always required)
    requirements.append(("bank_statement", "BANKING", True))
    requirements.append(("void_cheque", "BANKING", True))
    
    # CMHC: If LTV > 80%, require insurance-related docs
    if application.ltv > Decimal('80.00'):
        requirements.append(("gift_letter", "DOWN_PAYMENT", application.down_payment_gift > 0))
    
    return requirements
```

### 3.3 Document Status State Machine
```
pending → accepted (on verify)
pending → rejected (on reject)
accepted → rejected (NOT ALLOWED - must delete and re-upload)
rejected → pending (NOT ALLOWED - must re-upload)
any → soft-deleted (on delete, retains file)
```

**FINTRAC Compliance:** All state transitions logged with `created_by` timestamp.

### 3.4 Verification Workflow
**Underwriter Actions:**
1. Download document via presigned URL (if S3) or direct stream
2. Review against application data
3. **PIPEDA Warning:** Never log SIN or DOB from document content
4. Call verify/reject endpoint
5. System logs: `document_verified` event with `created_by`, `document_id`, `verification_notes`

**Identity Documents (FINTRAC Trigger):**
- Log explicit event: `identity_verification_completed`
- Include: `user_id`, `document_id`, `verification_timestamp`
- Retain for 5 years as per FINTRAC Record Keeping Requirements

### 3.5 Document Retention Policy
**FINTRAC 5-Year Rule:** All documents retained for 5 years from `uploaded_at`

**Automated Purge Job (runs monthly):**
```sql
DELETE FROM documents 
WHERE is_deleted = true 
  AND uploaded_at < NOW() - INTERVAL '5 years';
```

**CMHC Insurance Documents:** Retain for duration of mortgage + 7 years (separate flag `is_cmhc_insured`)

---

## 4. Migrations

### 4.1 New Tables
```sql
-- Create documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    verified_by UUID REFERENCES users(id),
    document_type VARCHAR(50) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL UNIQUE,
    file_size BIGINT NOT NULL CHECK (file_size > 0),
    mime_type VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    rejection_reason TEXT,
    rejection_details TEXT,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    verified_at TIMESTAMPTZ,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    checksum_sha256 CHAR(64) NOT NULL,
    conversion_applied VARCHAR(20),
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    deleted_at TIMESTAMPTZ,
    deleted_by UUID REFERENCES users(id)
);

-- Create document_requirements table
CREATE TABLE document_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL,
    category VARCHAR(30) NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT true,
    is_received BOOLEAN NOT NULL DEFAULT false,
    due_date TIMESTAMPTZ,
    received_document_id UUID REFERENCES documents(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(application_id, document_type)
);
```

### 4.2 Indexes
```sql
-- Documents indexes
CREATE INDEX idx_documents_app_type_deleted ON documents(application_id, document_type, is_deleted);
CREATE INDEX idx_documents_app_status_verified ON documents(application_id, status, is_verified);
CREATE INDEX idx_documents_uploader_date ON documents(uploaded_by, uploaded_at DESC);
CREATE INDEX idx_documents_checksum ON documents(checksum_sha256);

-- Requirements indexes
CREATE INDEX idx_requirements_app_received ON document_requirements(application_id, is_required, is_received);
CREATE INDEX idx_requirements_due_date ON document_requirements(due_date, is_received);

-- Partial index for active documents
CREATE INDEX idx_documents_active ON documents(application_id) WHERE is_deleted = false;
```

### 4.3 Trigger for updated_at
```sql
CREATE TRIGGER update_documents_updated_at 
BEFORE UPDATE ON documents 
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_requirements_updated_at 
BEFORE UPDATE ON document_requirements 
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## 5. Security & Compliance

### 5.1 PIPEDA Compliance
**Data Minimization:** Only collect document types explicitly required for underwriting decision.

**SIN Document Handling (proof_of_sin):**
- **Encryption at Rest:** File content encrypted using AES-256 via `cryptography.fernet`
  ```python
  from cryptography.fernet import Fernet
  key = settings.DOCUMENT_ENCRYPTION_KEY  # From Vault/KMS
  encrypted_content = Fernet(key).encrypt(file_content)
  ```
- **Never in Logs:** `file_path` contains UUID, not SIN. Checksum is SHA256 of encrypted content.
- **Lookup Hashing:** For duplicate detection, hash the *encrypted* file, not raw SIN.
- **API Responses:** `file_name` is sanitized; never returns original filename containing SIN.

### 5.2 FINTRAC Compliance
**Identity Verification Logging:**
```python
# On document verify (if document_type == "proof_of_sin" or "government_id")
logger.info("identity_verification_completed",
            event_type="fintrac_identity",
            user_id=current_user.id,
            document_id=document.id,
            application_id=application.id,
            verification_timestamp=verified_at,
            created_by=current_user.id,
            retention_years=5)
```

**Large Transaction Flagging:** If application.loan_amount > CAD $10,000 (always true for mortgages), log:
```python
logger.info("large_transaction_document_received",
            event_type="fintrac_large_transaction",
            transaction_amount=application.loan_amount,
            document_type=document_type,
            created_by=current_user.id)
```

**Record Immutability:** `documents` table has no UPDATE on `file_path`, `checksum`. Soft-delete only.

### 5.3 OSFI B-20 Indirect Impact
While OSFI B-20 governs ratio calculations, document verification status **blocks** underwriting:
- Underwriting service must check: `all(required_docs.is_verified == True)`
- If LTV > 80%, require `gift_letter` verification before CMHC premium calculation
- Log: `underwriting_blocked_missing_documents` if verification incomplete

### 5.4 Authentication & Authorization Matrix
| Endpoint | Borrower | Broker | Underwriter | Admin |
|----------|----------|--------|-------------|-------|
| GET checklist | ✓ Own apps | ✓ Own clients | ✓ All apps | ✓ All |
| POST upload | ✓ Own apps | ✓ Own clients | ✗ | ✗ |
| GET list | ✓ Own apps | ✓ Own clients | ✓ All apps | ✓ All |
| GET download | ✓ Own apps | ✓ Own clients | ✓ All apps | ✓ All |
| PUT verify | ✗ | ✗ | ✓ With perm | ✓ |
| PUT reject | ✗ | ✗ | ✓ With perm | ✓ |
| DELETE | ✓ Own uploads | ✓ Own clients | ✓ All apps | ✓ |

**Permission Check:** Use FastAPI dependency `requires_permission("document:verify")` for verification actions.

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy
```python
# Module-specific base exception
class DocumentException(AppException):
    """Base exception for document management module"""
    module_code = "DOC"

# Specific exception classes
class DocumentNotFoundError(DocumentException):
    http_status = 404
    error_code = "DOC_001"
    message_template = "Document {resource_id} not found"

class DocumentValidationError(DocumentException):
    http_status = 422
    error_code = "DOC_002"
    message_template = "Validation failed: {field} - {reason}"

class DocumentSizeExceededError(DocumentException):
    http_status = 400
    error_code = "DOC_004"
    message_template = "File size {actual} exceeds maximum {limit}MB"

class UnsupportedMimeTypeError(DocumentException):
    http_status = 400
    error_code = "DOC_005"
    message_template = "MIME type {mime} not supported. Allowed: {allowed}"

class VirusDetectedError(DocumentException):
    http_status = 400
    error_code = "DOC_006"
    message_template = "File failed virus scan"

class DuplicateDocumentError(DocumentException):
    http_status = 409
    error_code = "DOC_007"
    message_template = "Document type {doc_type} already received"

class DocumentAlreadyVerifiedError(DocumentException):
    http_status = 409
    error_code = "DOC_011"
    message_template = "Document {doc_id} already verified"
```

### Error Response Format
All errors return consistent JSON:
```json
{
  "detail": "Document abc-123 not found",
  "error_code": "DOC_001",
  "module": "document_management",
  "timestamp": "2024-01-10T14:30:00Z",
  "correlation_id": "req-abc-123",
  "request_id": "req-abc-123"
}
```

**Logging:** Use structlog with `error_code`, `user_id`, `application_id` but **NEVER** log `file_path` or PII content.

---

## 7. Missing Details Resolution

### 7.1 HEIC to PDF Conversion
**Library:** `pillow-heif` + `reportlab`
```bash
uv add pillow-heif reportlab
```
**Implementation:** Async worker process to avoid blocking upload
- Upload receives HEIC → store original → queue conversion job
- Worker converts to PDF → atomically replace file → update `conversion_applied`

### 7.2 Virus Scanning Timeline
**Phase 1 (MVP):** Log checksums only
**Phase 2 (Q2 2024):** Integrate ClamAV daemon
```python
# Future implementation
import clamd
cd = clamd.ClamdUnixSocket()
scan_result = cd.scan(file_path)
```

### 7.3 OCR Requirements
**Deferred:** Not in MVP scope. Future enhancement:
- Use AWS Textract or Google Document AI
- Extract text for automated validation (e.g., name matching)
- **PIPEDA Warning:** OCR output must be encrypted if contains SIN/DOB

### 7.4 Document Retention Policy
**Implementation:** Background Celery/Arq job
```python
@arq.task
async def purge_expired_documents():
    async with get_async_session() as session:
        result = await session.execute(
            delete(Document)
            .where(
                Document.is_deleted == True,
                Document.uploaded_at < datetime.utcnow() - timedelta(days=1825)
            )
        )
        logger.info("retention_purge_completed", deleted_count=result.rowcount)
```

### 7.5 S3 Integration Path
**Abstraction Layer:** Create `DocumentStorageService`
```python
class DocumentStorageService(Protocol):
    async def store(self, file_content: bytes, path: str) -> str: ...
    async def retrieve(self, path: str) -> bytes: ...
    async def delete(self, path: str) -> None: ...

# Implementations:
# - LocalFileStorage (current)
# - S3Storage (future: uv add aioboto3)
```
**Configuration:** `settings.DOCUMENT_STORAGE_BACKEND = "local" | "s3"`

---

## 8. Testing Strategy

### 8.1 Unit Tests
- File validation logic (MIME, size, sanitization)
- HEIC conversion pipeline
- Checksum generation
- State machine transitions

### 8.2 Integration Tests
- Full upload → verify → download flow
- FINTRAC audit log verification
- PIPEDA: Ensure SIN never in logs
- Concurrent uploads (race conditions)

### 8.3 Test Fixtures
```python
@pytest.fixture
def sample_pdf_file():
    return io.BytesIO(b"%PDF-1.4 mock content")

@pytest.fixture
def mock_document_requirements(db_session, application):
    return DocumentRequirementFactory(application=application, document_type="government_id")
```

---

## 9. Deployment Checklist

- [ ] Set `DOCUMENT_ENCRYPTION_KEY` in Vault/KMS (32-byte AES key)
- [ ] Configure `/uploads` directory with restricted permissions (0700)
- [ ] Set up log aggregation for `identity_verification_completed` events
- [ ] Enable Prometheus metrics: `document_upload_total`, `document_verified_total`
- [ ] Run `pip-audit` on `pillow-heif` and `reportlab`
- [ ] Create `.env.example` with `DOCUMENT_STORAGE_BACKEND=local`
- [ ] Document 5-year retention policy in ops runbook

---