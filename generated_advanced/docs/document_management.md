# Document Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Document Management Module Design Plan

**File:** `docs/design/document-management.md`  
**Module:** `modules/document_management/`  
**Complexity:** Reasoning

---

## 1. Endpoints

### 1.1 GET /api/v1/applications/{application_id}/documents/checklist
**Purpose:** Retrieve document requirement status for an application.

**Auth:** Authenticated user (borrower, broker, or underwriter).

**Response Schema:**
```python
class DocumentChecklistResponse(BaseModel):
    application_id: UUID
    requirements: List[DocumentRequirementItem]
    overall_status: Literal["complete", "incomplete", "overdue"]
    
class DocumentRequirementItem(BaseModel):
    document_type: DocumentTypeEnum
    is_required: bool
    is_received: bool
    due_date: Optional[datetime]
    days_until_due: Optional[int]
    uploaded_documents: List[DocumentSummary]
    
class DocumentSummary(BaseModel):
    doc_id: UUID
    file_name: str
    status: DocumentStatusEnum
    is_verified: bool
    uploaded_at: datetime
```

**Error Responses:**
- `404` `DOCUMENT_001` - Application not found
- `403` `DOCUMENT_004` - User lacks access to application
- `422` - Invalid UUID format

---

### 1.2 POST /api/v1/applications/{application_id}/documents/upload
**Purpose:** Upload a single document via multipart/form-data.

**Auth:** Authenticated user (borrower or broker).

**Request Schema:**
```python
class DocumentUploadRequest:
    document_type: DocumentTypeEnum  # Form field
    file: UploadFile                  # multipart file
```

**Response Schema:**
```python
class DocumentUploadResponse(BaseModel):
    doc_id: UUID
    file_name: str
    status: DocumentStatusEnum
    message: str
```

**Validation Rules:**
- MIME type: `application/pdf`, `image/jpeg`, `image/png`, `image/heic` only
- Max file size: 10MB (enforced via streaming read)
- File name sanitized to `[a-z0-9_.-]` only
- HEIC files automatically converted to PDF before storage

**Error Responses:**
- `400` `DOCUMENT_002` - Invalid MIME type or file size exceeded
- `422` `DOCUMENT_002` - Document type not allowed for application state
- `404` `DOCUMENT_001` - Application not found
- `409` `DOCUMENT_003` - Duplicate document type when only one allowed
- `413` - Payload too large (FastAPI default)

---

### 1.3 GET /api/v1/applications/{application_id}/documents
**Purpose:** List all uploaded documents for an application.

**Auth:** Authenticated user (borrower, broker, or underwriter).

**Response Schema:**
```python
class DocumentListResponse(BaseModel):
    application_id: UUID
    documents: List[DocumentDetail]
    
class DocumentDetail(BaseModel):
    doc_id: UUID
    document_type: DocumentTypeEnum
    file_name: str
    file_size: int
    mime_type: str
    status: DocumentStatusEnum
    is_verified: bool
    uploaded_by: UUID
    uploaded_at: datetime
    verified_by: Optional[UUID]
    verified_at: Optional[datetime]
    rejection_reason: Optional[str]
```

**Error Responses:**
- `404` `DOCUMENT_001` - Application not found
- `403` `DOCUMENT_004` - Access denied

---

### 1.4 GET /api/v1/applications/{application_id}/documents/{doc_id}/download
**Purpose:** Stream document file for download.

**Auth:** Authenticated user (underwriter only for IDENTITY docs; all roles for others).

**Response:** StreamingResponse with `application/pdf` or `image/jpeg/png` MIME type.

**Headers:**
- `Content-Disposition: attachment; filename="{sanitized_filename}"`

**Error Responses:**
- `404` `DOCUMENT_001` - Document not found
- `403` `DOCUMENT_004` - Insufficient privileges for document type
- `410` `DOCUMENT_006` - File no longer available (archived)

---

### 1.5 PUT /api/v1/applications/{application_id}/documents/{doc_id}/verify
**Purpose:** Mark document as verified by underwriter.

**Auth:** Underwriter role only.

**Request Schema:**
```python
class DocumentVerifyRequest(BaseModel):
    verified: bool = True
    notes: Optional[str] = Field(max_length=500)
```

**Response Schema:**
```python
class DocumentVerifyResponse(BaseModel):
    doc_id: UUID
    is_verified: bool
    verified_by: UUID
    verified_at: datetime
    message: str
```

**Business Rules:**
- Only `pending` documents can be verified
- Document must belong to application
- Triggers FINTRAC identity verification log if `document_type` in IDENTITY category

**Error Responses:**
- `404` `DOCUMENT_001` - Document not found
- `403` `DOCUMENT_004` - Insufficient privileges
- `409` `DOCUMENT_003` - Document not in pending state
- `422` - Notes exceed length limit

---

### 1.6 PUT /api/v1/applications/{application_id}/documents/{doc_id}/reject
**Purpose:** Reject document with reason.

**Auth:** Underwriter role only.

**Request Schema:**
```python
class DocumentRejectRequest(BaseModel):
    rejection_reason: str = Field(min_length=10, max_length=1000)
```

**Response Schema:**
```python
class DocumentRejectResponse(BaseModel):
    doc_id: UUID
    status: DocumentStatusEnum  # "rejected"
    rejection_reason: str
    message: str
```

**Business Rules:**
- Only `pending` documents can be rejected
- Rejection reason stored in audit log
- Notifies uploader via event (out of scope)

**Error Responses:**
- `404` `DOCUMENT_001` - Document not found
- `403` `DOCUMENT_004` - Insufficient privileges
- `409` `DOCUMENT_003` - Document not in pending state
- `422` - Rejection reason length invalid

---

### 1.7 DELETE /api/v1/applications/{application_id}/documents/{doc_id}
**Purpose:** Soft-delete document (sets status to `deleted`).

**Auth:** Original uploader or underwriter.

**Response:** `204 No Content`

**Business Rules:**
- Only `pending` or `rejected` documents can be deleted
- FINTRAC audit trail preserved (record retained, file marked deleted)
- Physical file deletion follows 5-year retention policy

**Error Responses:**
- `404` `DOCUMENT_001` - Document not found
- `403` `DOCUMENT_004` - Not original uploader or underwriter
- `409` `DOCUMENT_003` - Cannot delete verified documents

---

## 2. Models & Database

### 2.1 documents Table
```python
class Document(Base):
    __tablename__ = "documents"
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: UUID = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True)
    uploaded_by: UUID = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    document_type: DocumentTypeEnum = Column(SqlEnum(DocumentTypeEnum), nullable=False)
    
    # File metadata (file_path encrypted at rest)
    file_name: str = Column(String(255), nullable=False)  # Sanitized filename
    file_path: str = Column(EncryptedType(String(500)), nullable=False)  # AES-256 encryption
    file_size: int = Column(Integer, nullable=False)  # Bytes
    mime_type: str = Column(String(100), nullable=False)
    
    # Workflow state
    status: DocumentStatusEnum = Column(SqlEnum(DocumentStatusEnum), default="pending", nullable=False, index=True)
    rejection_reason: Optional[str] = Column(Text, nullable=True)
    is_verified: bool = Column(Boolean, default=False, nullable=False)
    verified_by: Optional[UUID] = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    verified_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    
    # Audit fields
    uploaded_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    application = relationship("Application", back_populates="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    verifier = relationship("User", foreign_keys=[verified_by])
    
    # Indexes
    __table_args__ = (
        Index("idx_documents_app_type", "application_id", "document_type"),
        Index("idx_documents_status", "status"),
        CheckConstraint("file_size <= 10485760", name="chk_max_file_size_10mb"),
    )
```

### 2.2 document_requirements Table
```python
class DocumentRequirement(Base):
    __tablename__ = "document_requirements"
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: UUID = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True)
    document_type: DocumentTypeEnum = Column(SqlEnum(DocumentTypeEnum), nullable=False)
    
    # Requirement tracking
    is_required: bool = Column(Boolean, nullable=False)
    is_received: bool = Column(Boolean, default=False, nullable=False)
    due_date: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    
    # Audit fields
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    application = relationship("Application", back_populates="document_requirements")
    
    # Indexes
    __table_args__ = (
        Index("idx_doc_req_app_type", "application_id", "document_type", unique=True),
        Index("idx_doc_req_overdue", "is_required", "is_received", "due_date"),
    )
```

### 2.3 Enums
```python
class DocumentTypeEnum(str, Enum):
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

class DocumentStatusEnum(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DELETED = "deleted"
```

---

## 3. Business Logic

### 3.1 Document Upload Flow
1. **Validation Phase**
   - Verify MIME type against allowed list
   - Stream file to calculate size; abort if >10MB
   - Sanitize filename: `re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)`
   - Generate storage path: `/uploads/{application_id}/{document_type}/{uuid}_{sanitized_filename}`

2. **HEIC Conversion**
   - If `mime_type == "image/heic"`:
     - Use `pillow-heif` library to convert to PDF
     - Update `mime_type` to `application/pdf`
     - Set `file_size` to converted PDF size

3. **Virus Scan Placeholder**
   - Calculate SHA256 hash of file content
   - Log: `{"event": "file_uploaded", "hash": "abc123...", "correlation_id": cid}` (no PII)
   - TODO: Integrate ClamAV daemon scan before marking `status=accepted`

4. **Storage**
   - Write file to encrypted volume (or S3 with SSE-KMS)
   - Encrypt file_path in database using AES-256 via `EncryptedType`

5. **Requirement Sync**
   - On successful upload, set `document_requirements.is_received = True` for matching type

### 3.2 Verification Workflow
- **Trigger:** Underwriter reviews document
- **FINTRAC Logging:** If `document_type` in `IDENTITY` category:
  ```python
  logger.info(
      "identity_verification_completed",
      correlation_id=correlation_id,
      user_id=underwriter_id,
      application_id=application_id,
      document_id=doc_id,
      verification_result=True
  )
  ```
- **State Update:** `is_verified=True`, `verified_at=now()`, `status=accepted`
- **Side Effect:** Advance application workflow if all required docs verified

### 3.3 Rejection Workflow
- **Validation:** Document must be `pending`
- **Audit:** Log rejection with reason (reason stored encrypted if contains PII)
- **Notification:** Publish `DocumentRejectedEvent` to message bus (out of scope)
- **State:** `status=rejected`, `is_verified=False`

### 3.4 Document Deletion (Soft)
- **Policy Enforcement:** Only `pending` or `rejected` docs deletable
- **Audit:** `status=deleted`, file marked for retention policy
- **Physical Deletion:** Not immediate; follows 5-year FINTRAC retention

### 3.5 Requirement Generation Logic
- On application creation, system generates `document_requirements` rows based on:
  - Loan type (purchase/refinance)
  - LTV ratio (if >80%, requires CMHC insurance docs)
  - Income type (salaried/self-employed)
  - Property type (condo requires `condo_status_cert`)

---

## 4. Migrations

### 4.1 New Tables
```sql
-- Create documents table
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    document_type document_type_enum NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,  -- Encrypted at rest via application layer
    file_size INTEGER NOT NULL CHECK (file_size <= 10485760),
    mime_type VARCHAR(100) NOT NULL,
    status document_status_enum DEFAULT 'pending' NOT NULL,
    rejection_reason TEXT,
    is_verified BOOLEAN DEFAULT FALSE NOT NULL,
    verified_by UUID REFERENCES users(id),
    verified_at TIMESTAMPTZ,
    uploaded_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_documents_app_type ON documents(application_id, document_type);
CREATE INDEX idx_documents_status ON documents(status);

-- Create document_requirements table
CREATE TABLE document_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type document_type_enum NOT NULL,
    is_required BOOLEAN NOT NULL,
    is_received BOOLEAN DEFAULT FALSE NOT NULL,
    due_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    UNIQUE(application_id, document_type)
);

CREATE INDEX idx_doc_req_app_type ON document_requirements(application_id, document_type);
CREATE INDEX idx_doc_req_overdue ON document_requirements(is_required, is_received, due_date) 
    WHERE is_required = TRUE AND is_received = FALSE;

-- Create enums
CREATE TYPE document_type_enum AS ENUM (...);
CREATE TYPE document_status_enum AS ENUM ('pending', 'accepted', 'rejected', 'deleted');
```

### 4.2 Indexes
- Composite indexes for common query patterns (application + type)
- Partial index for overdue requirement tracking

### 4.3 Data Migration
- **None** for new module. Future migration needed when adding new document types to existing applications.

---

## 5. Security & Compliance

### 5.1 FINTRAC Compliance
- **Identity Verification Logging:** All `document_type` in `IDENTITY` category generate immutable audit log on verification
- **5-Year Retention:** `documents` and `document_requirements` rows never hard-deleted; archived after 5 years to cold storage
- **Transaction Flagging:** Documents supporting transactions >CAD $10,000 must include `application.transaction_value` in audit context
- **Audit Trail:** Every state change (upload, verify, reject, delete) logged with `correlation_id`, `user_id`, `timestamp`

### 5.2 PIPEDA Compliance
- **PII Encryption:** `file_path` encrypted via AES-256 (SQLAlchemy `EncryptedType`). File content encrypted at rest by storage backend (S3 SSE-KMS or encrypted EBS volume)
- **Data Minimization:** Only collect document types strictly required for underwriting decision
- **No Logging:** File content, extracted text, or metadata containing SIN/DOB never logged. Hash logs contain no PII.
- **Access Control:** IDENTITY documents restricted to underwriters; other docs accessible to application stakeholders

### 5.3 OSFI B-20
- **Indirect Impact:** Document verification status feeds into `application.is_documentation_complete` flag, which gates rate calculation and approval. No direct ratio calculation in this module.

### 5.4 CMHC
- **Insurance Document Tracking:** When `application.ltv > 80%`, `document_requirements` auto-generates entries for `insurance_certificate` and `premium_payment_proof`

### 5.5 Authentication & Authorization
- **Endpoints:** All require JWT authentication via `Depends(verify_token)`
- **Role Checks:**
  - `upload`: `borrower`, `broker`
  - `list`, `checklist`: `borrower`, `broker`, `underwriter`
  - `download`: `underwriter` (IDENTITY), all roles (others)
  - `verify`, `reject`: `underwriter` only
  - `delete`: original uploader or `underwriter`

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `DocumentNotFoundError` | 404 | `DOCUMENT_001` | "Document {doc_id} not found" | Download non-existent doc |
| `DocumentValidationError` | 422 | `DOCUMENT_002` | "{field}: {reason}" | Invalid MIME type, size >10MB |
| `DocumentBusinessRuleError` | 409 | `DOCUMENT_003` | "{rule} violated: {detail}" | Verify already-verified doc |
| `DocumentAccessDeniedError` | 403 | `DOCUMENT_004` | "Access denied to document {doc_id}" | Borrower downloads IDENTITY doc |
| `DocumentRequirementNotFoundError` | 404 | `DOCUMENT_005` | "Requirement not found for {app_id}/{doc_type}" | Upload for non-required doc type |
| `FileNotAvailableError` | 410 | `DOCUMENT_006` | "File {doc_id} no longer available" | Download archived/deleted file |
| `VirusScanFailedError` | 422 | `DOCUMENT_007` | "Virus scan failed: {detail}" | ClamAV detects malware (future) |

**Implementation Notes:**
- All exceptions inherit from `common.exceptions.AppException`
- Error responses include `correlation_id` from request context
- Structured logging: `logger.error("document_validation_failed", error_code="DOCUMENT_002", detail=...)`

---

## 7. Implementation Considerations

### 7.1 HEIC Conversion
- **Library:** `pillow-heif` (production-ready, LGPL)
- **Process:** Convert HEIC → PIL Image → PDF via `reportlab`
- **Fallback:** Reject file if conversion fails
- **Performance:** Async conversion using `anyio.to_thread.run_sync`

### 7.2 Virus Scanning (Future)
- **Design:** ClamAV daemon via TCP socket
- **Placeholder:** SHA256 hash logged; future migration adds `virus_scan_status` column
- **Blocking:** Uploads remain `pending` until scan completes (async worker pattern)

### 7.3 Storage Strategy
- **Phase 1:** Local encrypted volume `/uploads` (EBS encryption)
- **Phase 2:** Migrate to S3 with versioning, lifecycle policies
- **Path Security:** Use UUID in path to prevent enumeration; never expose direct path

### 7.4 Document Retention
- **Active:** 2 years from application closure
- **Cold Storage:** Move to Glacier after 2 years
- **Purge:** After 5 years per FINTRAC, hard delete file and anonymize DB record

### 7.5 OCR & Validation (Future)
- **Scope:** Extract income from pay stubs, validate government ID format
- **Compliance:** OCR output must be encrypted; no PII logged
- **Trigger:** Optional underwriter tool, not auto-validation

---

## 8. Dependencies

```toml
# pyproject.toml additions
[project]
dependencies = [
    "pillow-heif>=0.13.0",  # HEIC conversion
    "reportlab>=4.0.0",     # PDF generation
    "python-magic>=0.4.27", # MIME type detection
    "pydantic[email]>=2.0.0",
]
```

**WARNING:** This design assumes `common.security.encrypt_pii()` handles AES-256 encryption with key rotation managed via `common.config.Settings`.