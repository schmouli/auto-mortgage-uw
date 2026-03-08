# Document Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Document Management Module Design Plan

**Feature Slug:** `document-management`  
**Module Path:** `modules/document_management/`  
**Design Doc:** `docs/design/document-management.md`

---

## 1. Endpoints

### 1.1 GET /api/v1/applications/{id}/documents/checklist
**Purpose:** Retrieve the document requirements checklist for a mortgage application.

**Authentication:** Authenticated user (must have access to the application).

**Path Parameters:**
- `id`: UUID of the mortgage application.

**Query Parameters:**
- None.

**Response Schema (200 OK):**
```json
{
  "application_id": "uuid",
  "checklist": [
    {
      "document_type": "t4_slip",
      "category": "INCOME",
      "is_required": true,
      "is_received": false,
      "due_date": "2024-01-15",
      "status": "overdue|pending|received",
      "received_at": "2024-01-10T14:30:00Z",
      "document_id": "uuid"
    }
  ],
  "overall_completion": {
    "required_received": 5,
    "required_total": 8,
    "percentage": 62.5
  }
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401 Unauthorized | AUTH_001 | "Missing or invalid authentication token" |
| 403 Forbidden | AUTH_002 | "User does not have access to application {id}" |
| 404 Not Found | DOC_001 | "Application {id} not found" |
| 422 Validation Error | DOC_002 | "Invalid UUID format for application_id" |

---

### 1.2 POST /api/v1/applications/{id}/documents/upload
**Purpose:** Upload a document via multipart/form-data.

**Authentication:** Authenticated user (borrower, broker, or underwriter).

**Path Parameters:**
- `id`: UUID of the mortgage application.

**Request Body (multipart/form-data):**
- `file`: Binary file data (max 10MB)
- `document_type`: String enum (e.g., "t4_slip")
- `description`: Optional string (max 255 chars)

**Response Schema (201 Created):**
```json
{
  "document_id": "uuid",
  "application_id": "uuid",
  "document_type": "t4_slip",
  "file_name": "t4_2023_sanitized.pdf",
  "file_size": 1048576,
  "mime_type": "application/pdf",
  "status": "pending",
  "is_verified": false,
  "uploaded_at": "2024-01-10T14:30:00Z",
  "uploaded_by": "uuid",
  "description": "T4 slip for 2023 tax year"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 400 Bad Request | DOC_003 | "File size exceeds 10MB limit" |
| 400 Bad Request | DOC_004 | "Invalid MIME type: {type}. Allowed: PDF, JPEG, PNG, HEIC" |
| 400 Bad Request | DOC_005 | "Document type {type} is not required for this application" |
| 409 Conflict | DOC_006 | "Document type {type} already uploaded and pending verification" |
| 422 Validation Error | DOC_002 | "Invalid document_type enum value" |

---

### 1.3 GET /api/v1/applications/{id}/documents
**Purpose:** List all uploaded documents for an application.

**Authentication:** Authenticated user with application access.

**Path Parameters:**
- `id`: UUID of the mortgage application.

**Query Parameters:**
- `status`: Optional filter (pending/accepted/rejected)
- `document_type`: Optional filter (enum)
- `is_verified`: Optional boolean filter

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
      "verified_at": "2024-01-11T09:15:00Z",
      "verified_by": "uuid",
      "uploaded_at": "2024-01-10T14:30:00Z",
      "uploaded_by": "uuid",
      "description": "T4 slip for 2023 tax year",
      "rejection_reason": null
    }
  ],
  "total_count": 1
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401/403 | AUTH_001/002 | Authentication/Authorization failure |
| 404 | DOC_001 | "Application {id} not found" |

---

### 1.4 GET /api/v1/applications/{id}/documents/{doc_id}/download
**Purpose:** Download document file stream.

**Authentication:** Authenticated user with application access.

**Path Parameters:**
- `id`: UUID of the mortgage application.
- `doc_id`: UUID of the document.

**Response:**
- `200 OK` with `Content-Type: application/octet-stream`
- `Content-Disposition: attachment; filename="sanitized_filename.pdf"`

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401/403 | AUTH_001/002 | Authentication/Authorization failure |
| 404 | DOC_007 | "Document {doc_id} not found for application {id}" |
| 409 | DOC_008 | "Document {doc_id} is rejected and cannot be downloaded" |

---

### 1.5 PUT /api/v1/applications/{id}/documents/{doc_id}/verify
**Purpose:** Mark a document as verified by an underwriter.

**Authentication:** Admin or underwriter role only.

**Path Parameters:**
- `id`: UUID of the mortgage application.
- `doc_id`: UUID of the document.

**Request Body:**
```json
{
  "verification_notes": "Optional string (max 500 chars)"
}
```

**Response Schema (200 OK):**
```json
{
  "document_id": "uuid",
  "status": "accepted",
  "is_verified": true,
  "verified_at": "2024-01-11T09:15:00Z",
  "verified_by": "uuid",
  "verification_notes": "Income verified against NOA"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401/403 | AUTH_001/003 | Authentication/Authorization failure (underwriter only) |
| 404 | DOC_007 | "Document {doc_id} not found" |
| 409 | DOC_009 | "Cannot verify document with status: rejected" |
| 409 | DOC_010 | "Document already verified" |

---

### 1.6 PUT /api/v1/applications/{id}/documents/{doc_id}/reject
**Purpose:** Reject a document with a mandatory reason.

**Authentication:** Admin or underwriter role only.

**Path Parameters:**
- `id`: UUID of the mortgage application.
- `doc_id`: UUID of the document.

**Request Body:**
```json
{
  "rejection_reason": "String (max 500 chars, required)",
  "request_reupload": true
}
```

**Response Schema (200 OK):**
```json
{
  "document_id": "uuid",
  "status": "rejected",
  "is_verified": false,
  "rejection_reason": "Document is blurry and unreadable",
  "request_reupload": true,
  "rejected_at": "2024-01-11T09:15:00Z",
  "rejected_by": "uuid"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 400 | DOC_011 | "rejection_reason is required and cannot be empty" |
| 401/403 | AUTH_001/003 | Authentication/Authorization failure |
| 404 | DOC_007 | "Document {doc_id} not found" |
| 409 | DOC_012 | "Cannot reject already verified document" |

---

### 1.7 DELETE /api/v1/applications/{id}/documents/{doc_id}
**Purpose:** Soft-delete a document (marks as deleted, file remains for retention).

**Authentication:** Owner of the document or admin role.

**Path Parameters:**
- `id`: UUID of the mortgage application.
- `doc_id`: UUID of the document.

**Response Schema (204 No Content):**

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 401/403 | AUTH_001/002 | Authentication/Authorization failure |
| 404 | DOC_007 | "Document {doc_id} not found" |
| 409 | DOC_013 | "Cannot delete verified document. Use reject workflow." |

---

## 2. Models & Database

### 2.1 documents Table
```python
class Document(Base):
    __tablename__ = "documents"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign Keys
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    
    # Document metadata
    document_type = Column(
        Enum(
            "government_id", "proof_of_sin", "t4_slip", "noa", "pay_stub",
            "employment_letter", "t1_general", "financial_statements",
            "rental_income_statement", "purchase_agreement", "mls_listing",
            "property_tax_bill", "condo_status_cert", "bank_statement",
            "void_cheque", "gift_letter", "rrsp_withdrawal_confirmation",
            "sale_proceeds_confirmation", "existing_mortgage_statement",
            "divorce_decree", "bankruptcy_discharge",
            name="document_type_enum"
        ),
        nullable=False,
        index=True
    )
    file_name = Column(String(255), nullable=False)  # Sanitized filename only
    file_path = Column(EncryptedType(String(500)), nullable=False)  # AES-256 encrypted full path
    file_size = Column(Integer, nullable=False)  # bytes
    mime_type = Column(String(100), nullable=False)
    
    # Workflow status
    status = Column(
        Enum("pending", "accepted", "rejected", name="doc_status_enum"),
        default="pending",
        nullable=False,
        index=True
    )
    rejection_reason = Column(Text, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False, index=True)
    verified_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Audit fields (mandatory)
    uploaded_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    application = relationship("Application", back_populates="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    verifier = relationship("User", foreign_keys=[verified_by])
    
    # Indexes
    __table_args__ = (
        Index("idx_documents_app_type_status", "application_id", "document_type", "status"),
        Index("idx_documents_verified", "is_verified", "verified_at"),
    )
```

### 2.2 document_requirements Table
```python
class DocumentRequirement(Base):
    __tablename__ = "document_requirements"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign Key
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True)
    
    # Requirement definition
    document_type = Column(
        Enum(..., name="document_type_enum"),  # Same enum as documents table
        nullable=False
    )
    is_required = Column(Boolean, default=True, nullable=False)
    is_received = Column(Boolean, default=False, nullable=False, index=True)
    due_date = Column(Date, nullable=True)  # Business day calculation
    
    # Audit fields (mandatory)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    application = relationship("Application", back_populates="document_requirements")
    
    # Indexes
    __table_args__ = (
        Index("idx_doc_req_app_received_due", "application_id", "is_received", "due_date"),
        UniqueConstraint("application_id", "document_type", name="uq_app_document_type"),
    )
```

---

## 3. Business Logic

### 3.1 File Upload Processing Pipeline
```python
async def process_upload(file: UploadFile, document_type: str, application_id: UUID):
    """
    1. Validation
       - MIME type check: application/pdf, image/jpeg, image/png, image/heic
       - File size check: ≤ 10MB (10 * 1024 * 1024 bytes)
       - Filename sanitization: strip `../`, special chars, limit to 255 chars
       - Duplicate check: prevent upload if same doc_type pending
    
    2. HEIC Conversion (if needed)
       - Use `pillow-heif` library
       - Convert to PDF with embedded JPEG
       - Update mime_type to "application/pdf"
       - Log conversion metadata with correlation_id
    
    3. Temporary Storage
       - Save to /tmp/{uuid}_pending.{ext}
       - Calculate SHA256 hash for virus scan placeholder
       - Log: "file_hash={hash} document_type={type} status=scanned_placeholder"
    
    4. Permanent Storage
       - Move to /uploads/{application_id}/{document_type}/{uuid}_{sanitized_name}
       - Encrypt file_path before DB storage
       - Set status = "pending", is_verified = False
    
    5. Update Requirements
       - Set document_requirements.is_received = True
       - Trigger event: "document_received"
    """
```

### 3.2 Document Verification Workflow
```python
async def verify_document(doc_id: UUID, user_id: UUID, notes: str):
    """
    Preconditions:
      - Document status == "pending"
      - User role in ["underwriter", "admin"]
    
    Actions:
      1. Update documents.status = "accepted"
      2. Set is_verified = True, verified_by = user_id, verified_at = now()
      3. Store verification_notes (encrypted if contains PII)
      4. Log audit: "document_verified" with doc_id, user_id, correlation_id
      5. Check if all required docs verified → trigger "application_ready_for_underwriting" event
    """
```

### 3.3 Checklist Generation Logic
```python
def generate_checklist(application_id: UUID):
    """
    1. Query application details (loan_amount, property_value, applicant_type)
    
    2. Determine required document_types:
       - IDENTITY: Always required (government_id, proof_of_sin)
       - INCOME: Based on employment_type (salaried, self_employed, rental_income)
       - PROPERTY: Always required (purchase_agreement, property_tax_bill)
       - BANKING: Always required (bank_statement_90d, void_cheque)
       - DOWN_PAYMENT: If LTV > 80% or gift funds involved
       - OTHER: Conditional (existing_mortgage_statement if refinance, divorce_decree if applicable)
    
    3. For each requirement:
       - Set due_date = application.created_at + 5 business days
       - Check documents table for existing uploads
       - Set is_received = True if pending/accepted doc exists
    
    4. Return aggregated checklist with status calculation
    """
```

### 3.4 Retention Policy Enforcement (Background Job)
```python
# Daily cron job: delete_soft_documents_older_than_retention()
"""
- IDENTITY docs: Retain 5 years (FINTRAC + PIPEDA)
- INCOME docs: Retain 5 years (FINTRAC)
- PROPERTY docs: Retain 7 years (CMHC claim period)
- BANKING: Retain 5 years
- DOWN_PAYMENT: Retain 5 years
- OTHER: Retain 5 years

Implementation:
  1. Query documents where uploaded_at < retention_date AND status = "accepted"
  2. Move files to glacier storage (S3)
  3. Update file_path to glacier URI (encrypted)
  4. Log retention action with correlation_id
"""
```

---

## 4. Migrations

### 4.1 New Tables
```python
# Alembic revision: create_document_management_tables

def upgrade():
    # Create document_type_enum
    op.execute("CREATE TYPE document_type_enum AS ENUM (...all types...)")
    
    # Create doc_status_enum
    op.execute("CREATE TYPE doc_status_enum AS ENUM ('pending', 'accepted', 'rejected')")
    
    # Create documents table
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("application_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("uploaded_by", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("verified_by", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("document_type", sa.Enum(...), nullable=False, index=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", EncryptedType(sa.String(500)), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("status", sa.Enum('pending', 'accepted', 'rejected'), default='pending', nullable=False, index=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("is_verified", sa.Boolean, default=False, nullable=False, index=True),
        sa.Column("verified_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("uploaded_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), onupdate=func.now(), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"]),
    )
    
    # Create composite indexes
    op.create_index("idx_documents_app_type_status", "documents", ["application_id", "document_type", "status"])
    op.create_index("idx_documents_verified", "documents", ["is_verified", "verified_at"])
    
    # Create document_requirements table
    op.create_table(
        "document_requirements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("application_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("document_type", sa.Enum(...), nullable=False),
        sa.Column("is_required", sa.Boolean, default=True, nullable=False),
        sa.Column("is_received", sa.Boolean, default=False, nullable=False, index=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), onupdate=func.now(), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("application_id", "document_type", name="uq_app_document_type"),
    )
    
    op.create_index("idx_doc_req_app_received_due", "document_requirements", ["application_id", "is_received", "due_date"])

def downgrade():
    op.drop_table("document_requirements")
    op.drop_table("documents")
    op.execute("DROP TYPE doc_status_enum")
    op.execute("DROP TYPE document_type_enum")
```

### 4.2 Data Migration (if any)
- None required for initial implementation.

---

## 5. Security & Compliance

### 5.1 FINTRAC Compliance
- **Audit Trail:** Every document action (upload, verify, reject, delete) is logged with `created_at`, `created_by` (immutable).
- **5-Year Retention:** All document records retained for 5+ years. Soft-delete only; files moved to glacier storage.
- **Transaction Reporting:** Documents tagged as `proof_of_sin` or `bank_statement` trigger enhanced logging for transactions > CAD $10,000.
- **Identity Verification:** `government_id` and `proof_of_sin` uploads log verification events with `correlation_id` for FINTRAC reporting.

### 5.2 PIPEDA Compliance
- **Encryption at Rest:** `file_path` column encrypted with AES-256 via `sqlalchemy-encrypted-type`. Files stored in encrypted S3 bucket.
- **Data Minimization:** Only collect document types strictly required for underwriting (see checklist logic).
- **PII Handling:** `file_name` sanitized to remove SIN, DOB, or account numbers. Never log file content or PII.
- **Hash for Lookups:** SHA256 hash of file content stored separately for duplicate detection (not linked to PII).

### 5.3 OSFI B-20 (Indirect)
- Document verification status feeds into underwriting decision engine. Unverified income documents block GDS/TDS calculations.
- Stress test documentation (`employment_letter`, `rental_income_statement`) must be verified before ratio calculations.

### 5.4 Access Control
- **Borrowers:** Can upload, list, download their own documents. Cannot verify/reject.
- **Brokers:** Can upload, list, download documents for their clients' applications.
- **Underwriters:** Full CRUD on verification/rejection. Cannot delete.
- **Admins:** Can delete documents (soft-delete only).

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `DocumentNotFoundError` | 404 | DOC_001 | "Application {id} not found" | Application UUID not in DB |
| `DocumentValidationError` | 422 | DOC_002 | "{field}: {reason}" | Pydantic validation failure |
| `DocumentSizeExceededError` | 400 | DOC_003 | "File size exceeds 10MB limit" | file_size > 10MB |
| `DocumentInvalidMimeError` | 400 | DOC_004 | "Invalid MIME type: {type}" | MIME not in allowlist |
| `DocumentNotRequiredError` | 400 | DOC_005 | "Document type {type} is not required" | Uploading non-required doc_type |
| `DocumentDuplicateError` | 409 | DOC_006 | "Document type {type} already uploaded" | Pending doc of same type exists |
| `DocumentNotFoundInAppError` | 404 | DOC_007 | "Document {doc_id} not found for application {id}" | doc_id not linked to app_id |
| `DocumentDownloadRejectedError` | 409 | DOC_008 | "Document {doc_id} is rejected" | Attempt to download rejected doc |
| `DocumentVerifyConflictError` | 409 | DOC_009 | "Cannot verify document with status: rejected" | Verify workflow on rejected doc |
| `DocumentAlreadyVerifiedError` | 409 | DOC_010 | "Document already verified" | Duplicate verification attempt |
| `DocumentRejectMissingReasonError` | 400 | DOC_011 | "rejection_reason is required" | Reject without reason field |
| `DocumentRejectVerifiedError` | 409 | DOC_012 | "Cannot reject already verified document" | Reject after verification |
| `DocumentDeleteVerifiedError` | 409 | DOC_013 | "Cannot delete verified document" | Delete instead of reject workflow |
| `DocumentVirusDetectedError` | 400 | DOC_014 | "Virus scan failed: {signature}" | Future ClamAV integration |
| `DocumentStorageError` | 500 | DOC_015 | "Failed to store document: {detail}" | S3/FS write failure |
| `DocumentEncryptionError` | 500 | DOC_016 | "Failed to encrypt file path" | Encryption library failure |

---

## 7. Missing Details & Future Considerations

### 7.1 HEIC to PDF Conversion
- **Library:** `pillow-heif` (Pillow plugin) + `reportlab` for PDF generation.
- **Implementation:** Convert HEIC → JPEG → Embed in PDF. Preserve EXIF metadata if needed.
- **Performance:** Async conversion with Celery worker if latency > 2s.
- **Quality:** JPEG quality=95, DPI=300 for readability.

### 7.2 Virus Scanning
- **Timeline:** Phase 2 (Q2 2024) integration with ClamAV daemon.
- **Placeholder:** Log file hash now; future: stream file to ClamAV socket.
- **Action on Detection:** Set status="rejected", rejection_reason="Virus detected: {signature}", alert security team.

### 7.3 OCR Requirements
- **Phase 3 (Q3 2024):** Integrate AWS Textract for income document validation.
- **Use Cases:** Verify T4 box values against self-reported income, detect tampering.
- **PII Risk:** OCR output must be encrypted and never logged. Purge after verification.

### 7.4 Document Retention Policy
| Document Category | Retention Period | Destruction Method |
|-------------------|------------------|-------------------|
| IDENTITY | 5 years | Glacier → Secure delete |
| INCOME | 5 years | Glacier → Secure delete |
| PROPERTY | 7 years | Glacier → Secure delete |
| BANKING | 5 years | Glacier → Secure delete |
| DOWN_PAYMENT | 5 years | Glacier → Secure delete |
| OTHER | 5 years | Glacier → Secure delete |

### 7.5 S3 Integration Path
- **Architecture:** Use `boto3` with async wrapper (`aioboto3`).
- **Bucket Structure:** `s3://mortgage-docs-{env}/{application_id}/{document_type}/{uuid}_{filename}`
- **Encryption:** SSE-KMS with per-application CMK.
- **Lifecycle:** Transition to Glacier after 30 days, delete after retention period.
- **Access:** Signed URLs for download (expires in 15 minutes), never expose bucket paths in API.

### 7.6 Background Jobs
- **Celery Beat:** Daily retention policy enforcement.
- **Celery Worker:** Async virus scanning, HEIC conversion, OCR processing.
- **Queue:** Separate queues for `docs_high_priority` (verification) and `docs_low_priority` (retention).

---

## 8. Testing Strategy

### 8.1 Unit Tests (`tests/unit/test_document_management.py`)
- File validation logic (MIME, size, sanitization)
- Checklist generation based on application type
- Encryption/decryption of file paths
- Error code mappings

### 8.2 Integration Tests (`tests/integration/test_document_management_integration.py`)
- Full upload → verify → download flow
- Reject and re-upload workflow
- Access control between user roles
- S3 signed URL generation
- HEIC conversion end-to-end

### 8.3 Compliance Tests (`tests/compliance/test_fintrac_document_retention.py`)
- Verify 5-year retention logic
- Audit log immutability
- PII encryption in database dumps

---

## 9. Observability

### 9.1 Logging (structlog)
```python
log.info(
    "document_uploaded",
    correlation_id=correlation_id,
    application_id=application_id,
    document_type=document_type,
    file_size=file_size,
    file_hash=sha256_hash,  # Safe to log (not PII)
    virus_scan_status="pending"
)
```

### 9.2 Metrics (Prometheus)
- `document_uploads_total{status="success|failure", type="..."}`
- `document_verification_duration_seconds`
- `document_retention_moves_total`
- `heic_conversion_failures_total`

### 9.3 Tracing (OpenTelemetry)
- Span per file processing step: validation, conversion, storage, DB update.
- Baggage: `application_id`, `document_type` for cross-service correlation.

---

## 10. Dependencies to Add (uv)

```bash
uv add sqlalchemy-encrypted-type[crypto]
uv add pillow pillow-heif reportlab
uv add python-magic  # MIME type detection
uv add aioboto3  # S3 async client
uv add celery  # Background jobs
```