# Document Management
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Document Management Module Design Plan

**Module Identifier:** `DOCUMENT`  
**Feature Slug:** `document-management`  
**Design Doc:** `docs/design/document-management.md`

---

## 1. Endpoints

### 1.1 GET /api/v1/applications/{id}/documents/checklist
**Authentication:** Authenticated user (borrower, broker, underwriter)  
**Authorization:** User must have `read:documents` scope and own the application or have `underwriter` role

**Request:** Path parameter `id: UUID`

**Response Schema:**
```json
{
  "application_id": "uuid",
  "checklist_items": [
    {
      "document_type": "enum",
      "is_required": "bool",
      "is_received": "bool",
      "due_date": "datetime | null",
      "received_documents": [
        {
          "document_id": "uuid",
          "file_name": "str",
          "status": "enum",
          "is_verified": "bool",
          "uploaded_at": "datetime"
        }
      ]
    }
  ]
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `DOCUMENT_001` | Application not found |
| 403 | `DOCUMENT_004` | User lacks permission to view this application's documents |
| 422 | `DOCUMENT_002` | Invalid application_id format |

---

### 1.2 POST /api/v1/applications/{id}/documents/upload
**Authentication:** Authenticated user  
**Authorization:** User must have `write:documents` scope and own the application

**Request:**
- Path parameter `id: UUID`
- Multipart form data:
  - `file: UploadFile` (required, max 10MB)
  - `document_type: str` (required, enum value)
  - `notes: str` (optional, max 500 chars)

**Response Schema:**
```json
{
  "document_id": "uuid",
  "application_id": "uuid",
  "document_type": "enum",
  "file_name": "str",
  "file_size": "int",
  "mime_type": "str",
  "status": "pending",
  "is_verified": false,
  "uploaded_at": "datetime"
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 400 | `DOCUMENT_005` | File size exceeds 10MB limit |
| 400 | `DOCUMENT_006` | Invalid MIME type (not in allowed list) |
| 400 | `DOCUMENT_007` | Document type not allowed for this application |
| 404 | `DOCUMENT_001` | Application not found |
| 403 | `DOCUMENT_004` | User lacks permission to upload |
| 422 | `DOCUMENT_002` | Invalid document_type enum value |
| 413 | `DOCUMENT_008` | Request entity too large |

**Business Logic Triggers:**
- Validates MIME type against whitelist: `application/pdf`, `image/jpeg`, `image/png`, `image/heic`
- Sanitizes filename (alphanumeric, dash, underscore only)
- Converts HEIC to PDF server-side
- Generates SHA256 hash for virus scan placeholder
- Stores file to `/uploads/{application_id}/{document_type}/{sanitized_filename}` (local) or S3 path
- Logs audit event: `document_uploaded` with correlation_id, user_id, application_id, document_type, file_hash (never filename)

---

### 1.3 GET /api/v1/applications/{id}/documents
**Authentication:** Authenticated user  
**Authorization:** User must have `read:documents` scope and own application or have `underwriter` role

**Request:** Path parameter `id: UUID`

**Response Schema:**
```json
{
  "application_id": "uuid",
  "documents": [
    {
      "document_id": "uuid",
      "document_type": "enum",
      "file_name": "str",
      "file_size": "int",
      "mime_type": "str",
      "status": "enum",
      "is_verified": "bool",
      "rejection_reason": "str | null",
      "uploaded_by": "uuid",
      "verified_by": "uuid | null",
      "uploaded_at": "datetime",
      "verified_at": "datetime | null"
    }
  ]
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `DOCUMENT_001` | Application not found |
| 403 | `DOCUMENT_004` | Permission denied |
| 422 | `DOCUMENT_002` | Invalid UUID format |

---

### 1.4 GET /api/v1/applications/{id}/documents/{doc_id}/download
**Authentication:** Authenticated user  
**Authorization:** User must have `read:documents` scope and own application or have `underwriter` role

**Request:**
- Path parameters: `id: UUID`, `doc_id: UUID`
- Query param: `download: bool = true` (trigger Content-Disposition attachment)

**Response:** 
- `200 OK` with file content as `application/octet-stream`
- Headers: `Content-Disposition: attachment; filename="sanitized_filename.pdf"`  
- **Never** includes internal file path in headers

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `DOCUMENT_009` | Document not found |
| 403 | `DOCUMENT_004` | Permission denied |
| 410 | `DOCUMENT_010` | Document deleted (soft-deleted, FINTRAC retention) |
| 422 | `DOCUMENT_002` | Invalid UUID format |

**Security Note:** File path decrypted from database, streamed directly from storage backend. Path never logged or exposed.

---

### 1.5 PUT /api/v1/applications/{id}/documents/{doc_id}/verify
**Authentication:** Authenticated user  
**Authorization:** `underwriter` role only (`underwriter:verify` scope)

**Request:**
- Path parameters: `id: UUID`, `doc_id: UUID`
- Body: `{"verified": true, "notes": "str | null"}`

**Response Schema:**
```json
{
  "document_id": "uuid",
  "status": "accepted",
  "is_verified": true,
  "verified_by": "uuid",
  "verified_at": "datetime",
  "notes": "str | null"
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `DOCUMENT_009` | Document not found |
| 403 | `DOCUMENT_011` | Insufficient privileges (not underwriter) |
| 409 | `DOCUMENT_003` | Document already verified |
| 422 | `DOCUMENT_002` | Invalid request body |

**Audit Trigger:** Logs `document_verified` event with underwriter_id, document_id, application_id, timestamp. Immutable audit record created.

---

### 1.6 PUT /api/v1/applications/{id}/documents/{doc_id}/reject
**Authentication:** Authenticated user  
**Authorization:** `underwriter` role only (`underwriter:reject` scope)

**Request:**
- Path parameters: `id: UUID`, `doc_id: UUID`
- Body: `{"rejection_reason": "str (required, min 10 chars)", "notes": "str | null"}`

**Response Schema:**
```json
{
  "document_id": "uuid",
  "status": "rejected",
  "is_verified": false,
  "rejection_reason": "str",
  "notes": "str | null",
  "rejected_by": "uuid",
  "rejected_at": "datetime"
}
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `DOCUMENT_009` | Document not found |
| 403 | `DOCUMENT_011` | Insufficient privileges |
| 409 | `DOCUMENT_003` | Cannot reject verified document (must unverify first) |
| 422 | `DOCUMENT_002` | Rejection reason too short |

---

### 1.7 DELETE /api/v1/applications/{id}/documents/{doc_id}
**Authentication:** Authenticated user  
**Authorization:** Owner can delete `pending` docs; `underwriter` can delete any status

**Request:** Path parameters: `id: UUID`, `doc_id: UUID`

**Response:** `204 No Content`

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `DOCUMENT_009` | Document not found |
| 403 | `DOCUMENT_004` | Permission denied |
| 409 | `DOCUMENT_012` | Owner cannot delete non-pending documents |

**Business Logic:** Implements **soft delete** for FINTRAC compliance. Sets `deleted_at` timestamp, retains metadata for 5 years. File moved to quarantine retention storage; metadata remains in database with `deleted` flag.

---

## 2. Models & Database

### 2.1 Document Model (`modules/document_management/models.py`)

```python
class Document(Base):
    __tablename__ = "documents"
    
    # Primary Key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # Foreign Keys
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    uploaded_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    verified_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )
    
    # Document Metadata
    document_type: Mapped[DocumentTypeEnum] = mapped_column(
        SQLAlchemyEnum(DocumentTypeEnum),
        nullable=False,
        index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)  # Sanitized name only
    file_path: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # AES-256 encrypted path
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Status Workflow
    status: Mapped[DocumentStatusEnum] = mapped_column(
        SQLAlchemyEnum(DocumentStatusEnum),
        default=DocumentStatusEnum.PENDING,
        nullable=False,
        index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # FINTRAC Compliance - Soft Delete
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    application: Mapped["Application"] = relationship(back_populates="documents")
    uploader: Mapped["User"] = relationship(foreign_keys=[uploaded_by])
    verifier: Mapped["User | None"] = relationship(foreign_keys=[verified_by])
    
    # Indexes
    __table_args__ = (
        # Composite index for common queries
        Index("idx_documents_app_status", "application_id", "status"),
        Index("idx_documents_app_type", "application_id", "document_type"),
        # Partial index for non-deleted documents
        Index("idx_documents_active", "deleted_at", postgresql_where=(deleted_at.is_(None))),
    )
```

**Encrypted Field Handling:**
- `file_path` stored as AES-256 encrypted bytes using `common/security.py:encrypt_pii()`
- Decryption only in service layer just before file access
- Key rotation support via `common/config.py:DOCUMENT_ENCRYPTION_KEY_ID`

---

### 2.2 DocumentRequirement Model

```python
class DocumentRequirement(Base):
    __tablename__ = "document_requirements"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    document_type: Mapped[DocumentTypeEnum] = mapped_column(
        SQLAlchemyEnum(DocumentTypeEnum),
        nullable=False,
        index=True
    )
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_received: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    application: Mapped["Application"] = relationship(back_populates="document_requirements")
    
    # Unique constraint per application+type
    __table_args__ = (
        UniqueConstraint("application_id", "document_type", name="uq_app_document_type"),
        Index("idx_requirements_app_received", "application_id", "is_received"),
    )
```

---

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
```

---

## 3. Business Logic

### 3.1 Document Upload Flow
```python
async def upload_document(
    application_id: UUID,
    file: UploadFile,
    document_type: DocumentTypeEnum,
    user_id: UUID
) -> Document:
    # 1. Validation
    validate_mime_type(file.content_type)
    validate_file_size(file.size)  # Max 10MB
    validate_document_type_for_application(application_id, document_type)
    
    # 2. Sanitization
    sanitized_name = sanitize_filename(file.filename)
    
    # 3. HEIC Conversion (if needed)
    if file.content_type == "image/heic":
        converted_pdf = await convert_heic_to_pdf(file)
        mime_type = "application/pdf"
        file_data = converted_pdf
    else:
        file_data = await file.read()
        mime_type = file.content_type
    
    # 4. Virus Scan Placeholder
    file_hash = hashlib.sha256(file_data).hexdigest()
    logger.info("document_uploaded", file_hash=file_hash, document_type=document_type)
    # Future: await virus_scan_service.scan(file_data, file_hash)
    
    # 5. Secure Storage Path
    storage_path = f"/uploads/{application_id}/{document_type.value}/{uuid4()}_{sanitized_name}"
    encrypted_path = encrypt_pii(storage_path)
    
    # 6. Persist to Storage
    await file_storage_service.save(storage_path, file_data)
    
    # 7. Create Database Record
    document = Document(
        application_id=application_id,
        uploaded_by=user_id,
        document_type=document_type,
        file_name=sanitized_name,
        file_path=encrypted_path,
        file_size=len(file_data),
        mime_type=mime_type,
        status=DocumentStatusEnum.PENDING
    )
    await db_session.add(document)
    
    # 8. Update Requirement Status
    await update_requirement_status(application_id, document_type, received=True)
    
    # 9. Audit Logging
    audit_service.log_event(
        event_type="document_uploaded",
        user_id=user_id,
        application_id=application_id,
        metadata={
            "document_id": document.id,
            "document_type": document_type.value,
            "file_hash": file_hash,
            "file_size": len(file_data)
        }
    )
    
    return document
```

### 3.2 Document Verification Flow
```python
async def verify_document(document_id: UUID, underwriter_id: UUID, notes: str | None):
    document = await get_document(document_id)
    
    if document.is_verified:
        raise DocumentAlreadyVerifiedError()
    
    document.status = DocumentStatusEnum.ACCEPTED
    document.is_verified = True
    document.verified_by = underwriter_id
    document.verified_at = datetime.now(timezone.utc)
    document.updated_at = datetime.now(timezone.utc)
    
    # Create immutable audit record
    audit_service.create_fintrac_record(
        event_type="document_verified",
        user_id=underwriter_id,
        application_id=document.application_id,
        transaction_amount=None,  # No monetary transaction
        metadata={
            "document_id": document_id,
            "document_type": document.document_type.value
        }
    )
    
    # Trigger underwriting workflow if all required docs verified
    await underwriting_service.check_document_completeness(document.application_id)
```

### 3.3 Document Rejection Flow
```python
async def reject_document(document_id: UUID, underwriter_id: UUID, reason: str, notes: str | None):
    document = await get_document(document_id)
    
    if document.is_verified:
        raise DocumentBusinessRuleError("Cannot reject verified document")
    
    document.status = DocumentStatusEnum.REJECTED
    document.rejection_reason = reason
    document.updated_at = datetime.now(timezone.utc)
    
    # Audit logging
    audit_service.log_event(
        event_type="document_rejected",
        user_id=underwriter_id,
        application_id=document.application_id,
        metadata={
            "document_id": document_id,
            "reason": reason
        }
    )
```

### 3.4 Document Deletion Flow (Soft Delete)
```python
async def delete_document(document_id: UUID, user_id: UUID, user_role: str):
    document = await get_document(document_id)
    
    # Permission check
    if user_role != "underwriter" and document.uploaded_by != user_id:
        raise DocumentPermissionError()
    if user_role != "underwriter" and document.status != DocumentStatusEnum.PENDING:
        raise DocumentBusinessRuleError("Only underwriters can delete non-pending documents")
    
    # Soft delete for FINTRAC retention
    document.deleted_at = datetime.now(timezone.utc)
    document.updated_at = datetime.now(timezone.utc)
    
    # Move file to quarantine retention
    await file_storage_service.quarantine(document.file_path)
    
    # Audit log (critical for FINTRAC)
    audit_service.create_fintrac_record(
        event_type="document_deleted",
        user_id=user_id,
        application_id=document.application_id,
        metadata={
            "document_id": document_id,
            "document_type": document.document_type.value,
            "retention_until": datetime.now(timezone.utc) + timedelta(days=1825)  # 5 years
        }
    )
```

### 3.5 Checklist Generation Logic
```python
async def generate_document_checklist(application_id: UUID) -> list[DocumentRequirement]:
    # 1. Determine required docs based on application data
    application = await get_application(application_id)
    
    required_types = set()
    
    # Always required
    required_types.update([
        DocumentTypeEnum.GOVERNMENT_ID,
        DocumentTypeEnum.PROOF_OF_SIN,
        DocumentTypeEnum.PAY_STUB,
        DocumentTypeEnum.BANK_STATEMENT
    ])
    
    # Conditional requirements
    if application.employment_type == "self_employed":
        required_types.add(DocumentTypeEnum.FINANCIAL_STATEMENTS)
        required_types.add(DocumentTypeEnum.T1_GENERAL)
    
    if application.loan_amount / application.property_value > 0.8:  # LTV > 80%
        required_types.add(DocumentTypeEnum.GIFT_LETTER)
    
    if application.property_type == "condo":
        required_types.add(DocumentTypeEnum.CONDO_STATUS_CERT)
    
    # 2. Upsert requirements
    for doc_type in required_types:
        await upsert_document_requirement(
            application_id=application_id,
            document_type=doc_type,
            is_required=True,
            due_date=application.submission_deadline
        )
    
    # 3. Return full checklist with status
    return await get_document_requirements(application_id)
```

---

## 4. Migrations

### 4.1 New Tables

**Migration File:** `alembic/versions/YYYYMMDDHHMMSS_create_document_management_tables.py`

```python
def upgrade():
    # Create ENUM types first
    op.execute("CREATE TYPE documenttypeenum AS ENUM ('government_id', 'proof_of_sin', 't4_slip', 'noa', 'pay_stub', 'employment_letter', 't1_general', 'financial_statements', 'rental_income_statement', 'purchase_agreement', 'mls_listing', 'property_tax_bill', 'condo_status_cert', 'bank_statement', 'void_cheque', 'gift_letter', 'rrsp_withdrawal_confirmation', 'sale_proceeds_confirmation', 'existing_mortgage_statement', 'divorce_decree', 'bankruptcy_discharge')")
    
    op.execute("CREATE TYPE documentstatusenum AS ENUM ('pending', 'accepted', 'rejected')")
    
    # documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("uploaded_by", sa.UUID(), nullable=False),
        sa.Column("verified_by", sa.UUID(), nullable=True),
        sa.Column("document_type", postgresql.ENUM("documenttypeenum"), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.LargeBinary(), nullable=False),  # Encrypted
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(50), nullable=False),
        sa.Column("status", postgresql.ENUM("documentstatusenum"), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id")
    )
    
    # Indexes
    op.create_index("idx_documents_app_status", "documents", ["application_id", "status"])
    op.create_index("idx_documents_app_type", "documents", ["application_id", "document_type"])
    op.create_index("idx_documents_active", "documents", ["deleted_at"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_documents_uploaded_by", "documents", ["uploaded_by"])
    
    # document_requirements table
    op.create_table(
        "document_requirements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("document_type", postgresql.ENUM("documenttypeenum"), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("is_received", sa.Boolean(), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "document_type", name="uq_app_document_type")
    )
    
    op.create_index("idx_requirements_app_received", "document_requirements", ["application_id", "is_received"])
    op.create_index("idx_requirements_due_date", "document_requirements", ["due_date"])
```

### 4.2 Data Migration Needs
- **Initial Seed:** None required
- **Backfill:** For existing applications, run `asyncio.gather` to generate document requirements based on current application state
- **Retention Policy:** Add scheduled job to move files to glacier storage after 1 year (configurable)

---

## 5. Security & Compliance

### 5.1 PIPEDA Requirements
- **Encryption at Rest:**
  - `file_path` encrypted with AES-256-GCM via `encrypt_pii()`
  - File content encryption: Use S3 SSE-KMS or local AES-256 encryption per file
  - Identity documents (`government_id`, `proof_of_sin`) tagged with `pii_level: critical` for enhanced encryption

- **Data Minimization:**
  - Only store required metadata (file_name, size, mime_type)
  - Never log file content, SIN, DOB, or banking details
  - Hash-based deduplication using SHA256 (not reversible)

- **PII Lookup:** Use `SHA256(sin_number)` for document correlation, never plaintext SIN in URLs or logs

### 5.2 FINTRAC Compliance
- **Immutable Audit Trail:**
  - All document events (`uploaded`, `verified`, `rejected`, `deleted`) create records in `audit_logs` table
  - `audit_logs` table has `created_at`, `created_by`, and **no update/delete** permissions at DB level
  - Retention: 5 years from `created_at` (soft delete only, hard delete prohibited)

- **Large Transaction Flagging:**
  - If application.loan_amount > 10_000: Add `fintrac_review_required` flag to document verification step
  - Logs include `transaction_threshold_exceeded: true` for audit

### 5.3 OSFI B-20 Integration
- Document verification status is **gating** for underwriting calculation
- Underwriting service calls `document_management.is_application_complete(application_id)` before GDS/TDS calculation
- Missing verified identity docs → underwriting blocked with error code `UNDERWRITING_015`

### 5.4 Access Control Matrix
| Role | Upload | View | Verify | Reject | Delete | Download |
|------|--------|------|--------|--------|--------|----------|
| borrower (owner) | ✅ Own apps | ✅ Own apps | ❌ | ❌ | ✅ Only pending | ✅ Own apps |
| broker | ✅ Assigned apps | ✅ Assigned apps | ❌ | ❌ | ❌ | ✅ Assigned apps |
| underwriter | ❌ | ✅ All apps | ✅ All apps | ✅ All apps | ✅ All apps | ✅ All apps |
| admin | ❌ | ✅ All apps | ❌ | ❌ | ✅ All apps | ✅ All apps |

**Implementation:** Use FastAPI dependencies:
- `require_application_ownership()`
- `require_underwriter_role()`
- `require_permission("write:documents")`

---

## 6. Error Codes & HTTP Responses

### 6.1 Exception Hierarchy
```python
# modules/document_management/exceptions.py

class DocumentManagementError(AppException):
    """Base exception for document management module"""
    module_code = "DOCUMENT"

class DocumentNotFoundError(DocumentManagementError):
    """Document or application not found"""
    http_status = 404
    error_code = "DOCUMENT_001"
    message_pattern = "Document {resource_id} not found"

class DocumentValidationError(DocumentManagementError):
    """Invalid input data"""
    http_status = 422
    error_code = "DOCUMENT_002"
    message_pattern = "{field}: {reason}"

class DocumentBusinessRuleError(DocumentManagementError):
    """Business rule violation (e.g., already verified)"""
    http_status = 409
    error_code = "DOCUMENT_003"
    message_pattern = "Business rule violated: {detail}"

class DocumentPermissionError(DocumentManagementError):
    """Insufficient permissions"""
    http_status = 403
    error_code = "DOCUMENT_004"
    message_pattern = "Permission denied: {resource}"

class DocumentSizeExceededError(DocumentManagementError):
    """File > 10MB"""
    http_status = 400
    error_code = "DOCUMENT_005"
    message_pattern = "File size {actual} exceeds limit of 10485760 bytes"

class DocumentMimeTypeError(DocumentManagementError):
    """Invalid file type"""
    http_status = 400
    error_code = "DOCUMENT_006"
    message_pattern = "MIME type {mime} not in allowed list"

class DocumentTypeNotAllowedError(DocumentManagementError):
    """Document type not required for this application"""
    http_status = 400
    error_code = "DOCUMENT_007"
    message_pattern = "Document type {doc_type} not required"

class DocumentEntityTooLargeError(DocumentManagementError):
    """Request size exceeds server limit"""
    http_status = 413
    error_code = "DOCUMENT_008"
    message_pattern = "Request entity too large"

class DocumentGoneError(DocumentManagementError):
    """Document was soft-deleted"""
    http_status = 410
    error_code = "DOCUMENT_010"
    message_pattern = "Document {doc_id} has been deleted"
```

### 6.2 Global Error Handler Mapping
```python
# common/exceptions.py mapping

EXCEPTION_MAP = {
    DocumentNotFoundError: (404, {"error_code": "DOCUMENT_001"}),
    DocumentValidationError: (422, {"error_code": "DOCUMENT_002"}),
    DocumentBusinessRuleError: (409, {"error_code": "DOCUMENT_003"}),
    DocumentPermissionError: (403, {"error_code": "DOCUMENT_004"}),
    # ... etc
}
```

---

## 7. Missing Details Resolution

### 7.1 HEIC to PDF Conversion
**Library:** `pillow-heif==1.16.0` + `reportlab==4.0.7`  
**Implementation:** `services/heic_converter.py`
```python
async def convert_heic_to_pdf(upload_file: UploadFile) -> bytes:
    image = Image.open(upload_file.file)
    pdf_buffer = io.BytesIO()
    image.save(pdf_buffer, format="PDF")
    return pdf_buffer.getvalue()
```
**Performance:** Async thread pool executor for CPU-bound conversion

### 7.2 Virus Scanning Timeline
**Phase 1 (MVP):** Log file hash only  
**Phase 2 (Q2 2024):** Integrate ClamAV via `clamd` Python client  
**Phase 3 (Q3 2024):** Enterprise solution with Sophos/McAfee API

### 7.3 OCR Requirements
**Out of Scope for MVP**  
**Future:** Integrate AWS Textract or Google Document AI for:
- Automatic SIN detection & redaction
- Income validation from T4s
- Address extraction from IDs

### 7.4 Document Retention Policy
| Document Type | Active Period | Archive Period | Destruction |
|---------------|---------------|----------------|-------------|
| IDENTITY | 7 years | 5 years | Shred after 12 years |
| INCOME | Loan term + 1 year | 5 years | Shred after 6 years |
| PROPERTY | Loan term + 1 year | 5 years | Shred after 6 years |
| BANKING | 1 year | 5 years | Shred after 6 years |

**Implementation:** `services/retention_service.py` with daily cron job

### 7.5 S3 Integration Path
**Architecture:**
```python
# common/config.py
class StorageConfig(BaseSettings):
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    S3_BUCKET: str = "mortgage-documents-prod"
    S3_KMS_KEY_ID: str = "arn:aws:kms:..."
    S3_SSE: bool = True
    
# services/file_storage.py
class FileStorageService:
    async def save(self, path: str, data: bytes):
        if config.STORAGE_BACKEND == "s3":
            await self.s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=path,
                Body=data,
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.S3_KMS_KEY_ID
            )
        else:
            # Local file system
            ...
```

**Migration Strategy:** Start with local storage, switch to S3 with feature flag

---

## 8. Testing Strategy

### 8.1 Unit Tests (`tests/unit/test_document_management.py`)
- Test filename sanitization: `test_sanitize_filename_removes_special_chars()`
- Test HEIC conversion: `test_convert_heic_to_pdf_success()`
- Test encryption: `test_file_path_encryption_roundtrip()`
- Test validation rules: `test_mime_type_whitelist()`

### 8.2 Integration Tests (`tests/integration/test_document_management_integration.py`)
- Full upload → verify → download flow
- Permission matrix testing
- Soft delete retention verification
- Concurrent upload handling

### 8.3 Compliance Tests
- FINTRAC audit immutability: `test_audit_log_cannot_be_modified()`
- PIPEDA encryption: `test_pii_fields_encrypted_at_rest()`
- Retention policy: `test_document_soft_deleted_not_purged()`

---

## 9. Observability

### 9.1 Logging
```python
# All service methods include
logger.bind(
    correlation_id=request.state.correlation_id,
    application_id=application_id,
    document_id=document_id,
    user_id=user_id
).info("document_action", action="upload", status="success")
```

**Never log:** `file_path`, `file_name` (contains PII), file content

### 9.2 Metrics (Prometheus)
- `document_upload_total{status="success|failure", type}`
- `document_verification_duration_seconds`
- `document_storage_bytes_total{type}`
- `document_virus_scan_failures_total`

---

## 10. Dependencies

```bash
# Add to pyproject.toml
uv add "fastapi[all]" sqlalchemy alembic asyncpg
uv add python-multipart python-magic  # MIME type detection
uv add "pillow-heif>=1.16.0" reportlab  # HEIC conversion
uv add pycryptodome  # AES encryption
uv add structlog
```

---

**WARNING:** This design assumes `modules/application/models.py` exists with `Application` model and `applications` table. If not present, add ForeignKey dependency check in migration.