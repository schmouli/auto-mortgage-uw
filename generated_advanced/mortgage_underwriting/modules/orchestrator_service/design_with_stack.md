# Design: Orchestrator Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

```markdown
docs/design/orchestrator-service.md
```

# Orchestrator Service Design Plan

## 1. Endpoints

### Application Submission & Management

#### `POST /api/v1/applications`
Submit new mortgage application with PDF documents.

**Authentication:** Authenticated (lender or broker JWT)

**Request Body (multipart/form-data):**
```python
class ApplicationSubmitRequest(BaseModel):
    borrower_data: BorrowerCreateSchema  # JSON string
    property_value: Decimal  # > 0
    purchase_price: Decimal  # > 0, >= property_value
    mortgage_amount: Decimal  # > 0, <= purchase_price
    lender_id: UUID
    documents: List[UploadFile]  # PDFs: ID, income proof, property docs
```

**Response (201 Created):**
```python
class ApplicationSubmitResponse(BaseModel):
    application_id: UUID
    status: Literal["submitted", "extracting"]
    submitted_at: datetime
    estimated_completion: datetime
```

**Error Responses:**
- `422` (ORCH_002): Invalid file type, missing required documents, financial values ≤ 0
- `400` (ORCH_004): Mortgage amount exceeds purchase price
- `401`: Invalid or missing JWT
- `403`: User not authorized for specified lender

---

#### `GET /api/v1/applications/{id}`
Retrieve application status and underwriting decision.

**Authentication:** Authenticated (lender, broker, or admin JWT)

**Response (200 OK):**
```python
class ApplicationStatusResponse(BaseModel):
    application_id: UUID
    status: ApplicationStatusEnum
    borrower: BorrowerResponseSchema  # PII encrypted fields masked
    property_value: Decimal
    purchase_price: Decimal
    mortgage_amount: Decimal
    ltv_ratio: Decimal  # Calculated: mortgage_amount / property_value
    cmhc_insurance_required: bool
    cmhc_premium: Optional[Decimal]
    gds_ratio: Optional[Decimal]  # Only if decided
    tds_ratio: Optional[Decimal]
    decision: Optional[Literal["approved", "rejected", "exception"]]
    decision_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
```

**Error Responses:**
- `404` (ORCH_001): Application not found
- `401`: Invalid JWT
- `403`: User lacks access to this application

---

#### `GET /api/v1/applications/{id}/documents`
List uploaded documents metadata (no PII exposure).

**Authentication:** Authenticated

**Response (200 OK):**
```python
class DocumentListResponse(BaseModel):
    application_id: UUID
    documents: List[DocumentMetadataSchema]

class DocumentMetadataSchema(BaseModel):
    document_id: UUID
    document_type: DocumentTypeEnum
    s3_key: str  # MinIO path
    file_size_bytes: int
    checksum_sha256: str
    uploaded_at: datetime
```

**Error Responses:**
- `404` (ORCH_001): Application not found
- `401`: Invalid JWT

---

#### `POST /api/v1/applications/{id}/reprocess`
Trigger reprocessing for failed or manually reviewed applications.

**Authentication:** Admin-only JWT

**Request Body:**
```python
class ReprocessRequest(BaseModel):
    reason: str  # Min 10 chars
    reset_documents: bool = False  # Re-upload docs flag
```

**Response (202 Accepted):**
```python
class ReprocessResponse(BaseModel):
    application_id: UUID
    new_status: Literal["submitted", "extracting"]
    reprocess_token: str  # Idempotency token
```

**Error Responses:**
- `409` (ORCH_003): Cannot reprocess - status must be 'exception' or 'decided'
- `404` (ORCH_001): Application not found
- `422` (ORCH_002): Reason too short
- `403`: Admin role required

---

#### `GET /api/v1/applications`
List applications with pagination and filtering.

**Authentication:** Authenticated

**Query Parameters:**
- `page`: int ≥ 1 (default: 1)
- `page_size`: int [10-100] (default: 20)
- `status`: Optional[ApplicationStatusEnum]
- `lender_id`: Optional[UUID]
- `borrower_sin_hash`: Optional[str]  # SHA256 hash for lookup

**Response (200 OK):**
```python
class ApplicationListResponse(BaseModel):
    page: int
    page_size: int
    total_count: int
    applications: List[ApplicationSummarySchema]

class ApplicationSummarySchema(BaseModel):
    application_id: UUID
    status: ApplicationStatusEnum
    borrower_name_masked: str  # Last 4 chars only
    mortgage_amount: Decimal
    created_at: datetime
```

**Error Responses:**
- `422` (ORCH_002): Invalid pagination params
- `401`: Invalid JWT

---

### FINTRAC Compliance Endpoints

#### `POST /api/v1/fintrac/applications/{id}/verify-identity`
Log identity verification attempt (mandatory audit trail).

**Authentication:** Authenticated

**Request Body:**
```python
class IdentityVerificationRequest(BaseModel):
    verification_method: Literal["document", "electronic", "third_party"]
    verified_by: UUID  # User ID
    notes: Optional[str]  # Max 500 chars
```

**Response (201 Created):**
```python
class IdentityVerificationResponse(BaseModel):
    verification_id: UUID
    application_id: UUID
    verified_at: datetime
    fintrac_reportable: bool  # True if mortgage_amount ≥ 10_000 CAD
```

**Error Responses:**
- `404` (ORCH_001): Application not found
- `422` (ORCH_002): Invalid verification method
- `401`: Invalid JWT

---

#### `GET /api/v1/fintrac/applications/{id}/verification`
Get FINTRAC verification status and audit trail.

**Authentication:** Authenticated

**Response (200 OK):**
```python
class VerificationStatusResponse(BaseModel):
    application_id: UUID
    verifications: List[VerificationRecordSchema]
    risk_flags: List[str]  # e.g., ["high_value_transaction", "new_client"]

class VerificationRecordSchema(BaseModel):
    verification_id: UUID
    method: str
    verified_at: datetime
    verified_by: UUID
    fintrac_report_filed: bool
```

**Error Responses:**
- `404` (ORCH_001): Application not found
- `401`: Invalid JWT

---

#### `POST /api/v1/fintrac/applications/{id}/report-transaction`
File FINTRAC Large Cash Transaction Report (LCTR) if applicable.

**Authentication:** Admin-only JWT

**Request Body:**
```python
class FintracReportRequest(BaseModel):
    transaction_type: Literal["mortgage_funding", "down_payment"]
    transaction_amount: Decimal  # Must be ≥ 10_000
    transaction_date: date
```

**Response (201 Created):**
```python
class FintracReportResponse(BaseModel):
    report_id: UUID
    fintrac_reference_number: str
    filed_at: datetime
    retention_until: datetime  # 5 years from filed_at
```

**Error Responses:**
- `422` (ORCH_005): Transaction amount < $10,000 threshold
- `409` (ORCH_003): Report already filed for this transaction
- `404` (ORCH_001): Application not found
- `403`: Admin role required

---

#### `GET /api/v1/fintrac/risk-assessment/{client_id}`
Retrieve consolidated client risk assessment across all applications.

**Authentication:** Admin-only JWT

**Response (200 OK):**
```python
class RiskAssessmentResponse(BaseModel):
    client_id: UUID
    sin_hash: str
    total_exposure: Decimal  # Sum of all mortgage amounts
    application_count: int
    risk_score: int  # 0-100
    risk_factors: List[str]  # e.g., ["multiple_recent_applications", "high_tds"]
    last_updated: datetime
```

**Error Responses:**
- `404` (ORCH_006): Client risk profile not found
- `401`: Invalid JWT
- `403`: Admin role required

---

## 2. Models & Database

### `applications` Table
```python
class Application(Base):
    __tablename__ = "applications"
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    borrower_id: UUID = Column(UUID(as_uuid=True), ForeignKey("borrowers.id"), nullable=False, index=True)
    lender_id: UUID = Column(UUID(as_uuid=True), ForeignKey("lenders.id"), nullable=False, index=True)
    
    status: ApplicationStatusEnum = Column(
        Enum("submitted", "extracting", "evaluating", "decided", "exception", name="app_status"),
        nullable=False,
        index=True
    )
    
    property_value: Decimal = Column(Numeric(precision=12, scale=2), nullable=False)
    purchase_price: Decimal = Column(Numeric(precision=12, scale=2), nullable=False)
    mortgage_amount: Decimal = Column(Numeric(precision=12, scale=2), nullable=False)
    
    # CMHC fields
    cmhc_insurance_required: bool = Column(Boolean, default=False, nullable=False)
    cmhc_premium: Decimal = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # Decision fields
    gds_ratio: Decimal = Column(Numeric(precision=5, scale=2), nullable=True)
    tds_ratio: Decimal = Column(Numeric(precision=5, scale=2), nullable=True)
    qualifying_rate: Decimal = Column(Numeric(precision=5, scale=4), nullable=True)  # OSFI stress test rate
    decision: String = Column(String(20), nullable=True)  # approved, rejected, exception
    decision_reason: Text = Column(Text, nullable=True)
    
    # Audit
    created_at: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: datetime = Column(DateTime(timezone=True), nullable=False, onupdate=func.now())
    
    # Relationships
    borrower = relationship("Borrower", back_populates="applications")
    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("mortgage_amount <= purchase_price", name="chk_mortgage_not_exceed_price"),
        CheckConstraint("property_value > 0", name="chk_property_value_positive"),
        Index("idx_applications_lender_status", "lender_id", "status"),
    )
```

### `borrowers` Table
```python
class Borrower(Base):
    __tablename__ = "borrowers"
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # PII - Encrypted at rest (AES-256)
    full_name_encrypted: bytes = Column(LargeBinary, nullable=False)
    
    # SIN - Hashed for lookups (SHA256), encrypted for storage
    sin_hash: String = Column(String(64), nullable=False, unique=True, index=True)  # SHA256 hex digest
    sin_encrypted: bytes = Column(LargeBinary, nullable=False)
    
    employment_type: EmploymentEnum = Column(
        Enum("salaried", "self_employed", "contract", name="employment_type"),
        nullable=False,
        index=True
    )
    
    gross_income: Decimal = Column(Numeric(precision=12, scale=2), nullable=False)
    credit_score: int = Column(Integer, nullable=False)
    
    # Audit
    created_at: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    applications = relationship("Application", back_populates="borrower")
    
    __table_args__ = (
        CheckConstraint("credit_score BETWEEN 300 AND 900", name="chk_credit_score_range"),
        CheckConstraint("gross_income > 0", name="chk_income_positive"),
    )
```

### `documents` Table
```python
class Document(Base):
    __tablename__ = "documents"
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id: UUID = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True)
    
    document_type: DocumentTypeEnum = Column(
        Enum("identification", "income_proof", "property_documents", "bank_statements", name="doc_type"),
        nullable=False,
        index=True
    )
    
    s3_bucket: String = Column(String(100), nullable=False)
    s3_key: String = Column(String(500), nullable=False, unique=True)
    file_size_bytes: int = Column(Integer, nullable=False)
    checksum_sha256: String = Column(String(64), nullable=False)  # For integrity verification
    
    # FINTRAC: Document immutable after upload
    created_at: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    application = relationship("Application", back_populates="documents")
    
    __table_args__ = (
        Index("idx_documents_app_type", "application_id", "document_type"),
    )
```

### `fintrac_verifications` Table (Audit Trail)
```python
class FintracVerification(Base):
    __tablename__ = "fintrac_verifications"
    
    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id: UUID = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True)
    
    verification_method: str = Column(String(50), nullable=False)
    verified_by: UUID = Column(UUID(as_uuid=True), nullable=False)
    notes: Text = Column(Text, nullable=True)
    
    # FINTRAC mandatory audit fields
    verified_at: datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fintrac_reportable: bool = Column(Boolean, nullable=False)
    report_filed: bool = Column(Boolean, default=False, nullable=False)
    
    # 5-year retention marker
    retention_until: datetime = Column(DateTime(timezone=True), nullable=False, server_default=text("now() + interval '5 years'"))
    
    __table_args__ = (
        Index("idx_verifications_app_reportable", "application_id", "fintrac_reportable"),
    )
```

---

## 3. Business Logic

### State Machine & Orchestration Flow

```python
# Celery Task Chain
@celery.task(bind=True, max_retries=3)
def extract_documents(application_id: UUID, document_ids: List[UUID]):
    """Extract data from PDFs using DocumentAI service"""
    # Timeout: 5 minutes per document
    # On failure: Update status to 'exception', log error
    # On success: Store extracted data, dispatch evaluate_policy

@celery.task(bind=True, max_retries=2)
def evaluate_policy(application_id: UUID):
    """Evaluate against lender policy rules"""
    # Timeout: 3 minutes
    # Calculate LTV, CMHC premium tiers
    # On failure: Update status to 'exception'
    # On success: Dispatch run_decision

@celery.task(bind=True, max_retries=1)
def run_decision(application_id: UUID):
    """Final underwriting decision with OSFI B-20 stress test"""
    # Timeout: 2 minutes
    # Calculate GDS/TDS with qualifying_rate = max(contract_rate + 2%, 5.25%)
    # Enforce GDS ≤ 39%, TDS ≤ 44%
    # Log full calculation breakdown for audit
    # Update status to 'decided'
```

### GDS/TDS Calculation (OSFI B-20)

**Formula:**
```
GDS = (PITH) / Gross Monthly Income
TDS = (PITH + Other Debts) / Gross Monthly Income

Where:
PITH = Principal + Interest + Property Taxes + Heating
Stress Test Rate = max(contract_rate + 2%, 5.25%)
```

**Implementation:**
1. Use extracted contract_rate from documents
2. Calculate qualifying_rate = max(contract_rate + Decimal('0.02'), Decimal('0.0525'))
3. Compute monthly payment at qualifying_rate using mortgage_amount
4. Fetch property tax estimate from property_value (industry standard: 1% annually)
5. Heating cost: fixed $100/month (OSFI guideline)
6. Validate: GDS ≤ 39% AND TDS ≤ 44%
7. Log: `structlog.bind(gds=gds_calc, tds=tds_calc, qualifying_rate=qual_rate, breakdown={...})`

### CMHC Insurance Logic

**LTV Calculation:**
```
ltv = (mortgage_amount / property_value) * 100
```

**Premium Tiers:**
- 80.01-85.00%: 2.80%
- 85.01-90.00%: 3.10%
- 90.01-95.00%: 4.00%

**Logic:**
```python
if ltv > Decimal('80.00'):
    cmhc_insurance_required = True
    if Decimal('80.01') <= ltv <= Decimal('85.00'):
        premium_rate = Decimal('0.0280')
    elif Decimal('85.01') <= ltv <= Decimal('90.00'):
        premium_rate = Decimal('0.0310')
    elif Decimal('90.01') <= ltv <= Decimal('95.00'):
        premium_rate = Decimal('0.0400')
    cmhc_premium = mortgage_amount * premium_rate
```

### FINTRAC Triggers

**Transaction Reporting Threshold:** $10,000 CAD
- If `mortgage_amount ≥ 10,000` → `fintrac_reportable = True`
- On identity verification → Log verification record with 5-year retention
- On document upload → Calculate checksum for immutability audit
- Admin must explicitly file report via `/report-transaction`

### Validation Rules

| Field | Validation | Error Code |
|-------|------------|------------|
| property_value | > 0, ≤ purchase_price | ORCH_002 |
| mortgage_amount | > 0, ≤ property_value * 0.95 (max LTV) | ORCH_002 |
| credit_score | 300-900 range | ORCH_002 |
| gross_income | > 0 | ORCH_002 |
| documents | Minimum 3 docs (ID, income, property) | ORCH_002 |
| SIN hash | Valid SHA256 hex (64 chars) | ORCH_002 |

---

## 4. Migrations

### New Tables
```python
# Alembic revision: create_orchestrator_tables

def upgrade():
    # Create ENUM types
    op.execute("CREATE TYPE app_status AS ENUM ('submitted', 'extracting', 'evaluating', 'decided', 'exception')")
    op.execute("CREATE TYPE employment_type AS ENUM ('salaried', 'self_employed', 'contract')")
    op.execute("CREATE TYPE doc_type AS ENUM ('identification', 'income_proof', 'property_documents', 'bank_statements')")
    
    # borrowers table
    op.create_table(
        "borrowers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("full_name_encrypted", LargeBinary, nullable=False),
        sa.Column("sin_hash", String(64), nullable=False, unique=True, index=True),
        sa.Column("sin_encrypted", LargeBinary, nullable=False),
        sa.Column("employment_type", Enum("salaried", "self_employed", "contract", name="employment_type"), nullable=False, index=True),
        sa.Column("gross_income", Numeric(precision=12, scale=2), nullable=False),
        sa.Column("credit_score", Integer, nullable=False),
        sa.Column("created_at", DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("credit_score BETWEEN 300 AND 900", name="chk_credit_score_range"),
        sa.CheckConstraint("gross_income > 0", name="chk_income_positive"),
    )
    
    # applications table
    op.create_table(
        "applications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("borrower_id", UUID(as_uuid=True), ForeignKey("borrowers.id"), nullable=False, index=True),
        sa.Column("lender_id", UUID(as_uuid=True), ForeignKey("lenders.id"), nullable=False, index=True),
        sa.Column("status", Enum("submitted", "extracting", "evaluating", "decided", "exception", name="app_status"), nullable=False, index=True),
        sa.Column("property_value", Numeric(precision=12, scale=2), nullable=False),
        sa.Column("purchase_price", Numeric(precision=12, scale=2), nullable=False),
        sa.Column("mortgage_amount", Numeric(precision=12, scale=2), nullable=False),
        sa.Column("cmhc_insurance_required", Boolean, default=False, nullable=False),
        sa.Column("cmhc_premium", Numeric(precision=10, scale=2), nullable=True),
        sa.Column("gds_ratio", Numeric(precision=5, scale=2), nullable=True),
        sa.Column("tds_ratio", Numeric(precision=5, scale=2), nullable=True),
        sa.Column("qualifying_rate", Numeric(precision=5, scale=4), nullable=True),
        sa.Column("decision", String(20), nullable=True),
        sa.Column("decision_reason", Text, nullable=True),
        sa.Column("created_at", DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", DateTime(timezone=True), nullable=False, onupdate=sa.func.now()),
        sa.CheckConstraint("mortgage_amount <= purchase_price", name="chk_mortgage_not_exceed_price"),
        sa.CheckConstraint("property_value > 0", name="chk_property_value_positive"),
    )
    op.create_index("idx_applications_lender_status", "applications", ["lender_id", "status"])
    
    # documents table
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("application_id", UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True),
        sa.Column("document_type", Enum("identification", "income_proof", "property_documents", "bank_statements", name="doc_type"), nullable=False, index=True),
        sa.Column("s3_bucket", String(100), nullable=False),
        sa.Column("s3_key", String(500), nullable=False, unique=True),
        sa.Column("file_size_bytes", Integer, nullable=False),
        sa.Column("checksum_sha256", String(64), nullable=False),
        sa.Column("created_at", DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_documents_app_type", "documents", ["application_id", "document_type"])
    
    # fintrac_verifications table
    op.create_table(
        "fintrac_verifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column("application_id", UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False, index=True),
        sa.Column("verification_method", String(50), nullable=False),
        sa.Column("verified_by", UUID(as_uuid=True), nullable=False),
        sa.Column("notes", Text, nullable=True),
        sa.Column("verified_at", DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("fintrac_reportable", Boolean, nullable=False),
        sa.Column("report_filed", Boolean, default=False, nullable=False),
        sa.Column("retention_until", DateTime(timezone=True), nullable=False, server_default=sa.text("now() + interval '5 years'")),
    )
    op.create_index("idx_verifications_app_reportable", "fintrac_verifications", ["application_id", "fintrac_reportable"])
```

### Data Migration Needs
- None for new tables. Existing borrower data migration handled in separate borrower management module.

---

## 5. Security & Compliance

### OSFI B-20 Implementation
- **Stress Test:** Qualifying rate calculated as `max(contract_rate + 2%, 5.25%)` in `run_decision` task
- **Hard Limits:** Enforced in decision logic: `if gds > 39% or tds > 44%: decision = "rejected"`
- **Audit Logging:** Every ratio calculation logged with `structlog` including:
  ```python
  log.bind(
      event="ratio_calculated",
      application_id=app_id,
      gds=gds_value,
      tds=tds_value,
      qualifying_rate=stress_rate,
      breakdown={
          "principal": p,
          "interest": i,
          "taxes": t,
          "heating": h,
          "other_debts": debts,
          "gross_income": income
      }
  )
  ```

### FINTRAC Requirements
- **Immutable Audit Trail:** `fintrac_verifications` table has no UPDATE/DELETE operations. All entries are INSERT-only.
- **Identity Verification:** Every verification attempt creates immutable record with 5-year retention (`retention_until` timestamp).
- **Transaction Threshold:** `mortgage_amount ≥ 10,000` triggers `fintrac_reportable = True`. Admin must file report via dedicated endpoint.
- **Document Integrity:** All documents stored with SHA256 checksum. Any tampering detected via checksum mismatch → status → 'exception'.

### CMHC Insurance Logic
- **LTV Calculation:** `ltv = mortgage_amount / property_value` using Decimal with 5+ precision
- **Premium Tiers:** Lookup in `evaluate_policy` task:
  ```python
  if ltv > 80:
      premium_rate = CMHC_TIERS.get(f"{ltv_low}-{ltv_high}")  # Decimal values
      cmhc_premium = mortgage_amount * premium_rate
  ```
- **Precision:** All financial calculations use `Decimal` with `quantize(Decimal('0.01'))` to prevent precision loss.

### PIPEDA Data Handling
- **Encryption at Rest:**
  - `borrowers.sin_encrypted`: AES-256-GCM encrypted SIN
  - `borrowers.full_name_encrypted`: AES-256-GCM encrypted full name
  - Encryption keys managed via `common/security.py` using KMS (never in codebase)
- **Hashing for Lookups:** `sin_hash` = SHA256(SIN) for index-based queries without exposing SIN
- **Data Minimization:** Only collect `gross_income`, `credit_score`, `employment_type` required for underwriting. No banking details stored.
- **Logging:** SIN, DOB, income, names NEVER appear in logs. Use `application_id` for correlation.

### Authentication & Authorization
- **JWT Required:** All endpoints except health checks
- **Role-Based Access:**
  - `POST /applications`: `broker`, `lender` roles
  - `GET /applications/*`: `broker`, `lender`, `admin` roles (lender filtered to own apps)
  - `POST /reprocess`: `admin` role only
  - `POST /fintrac/report-transaction`: `admin` role only
  - `GET /fintrac/risk-assessment`: `admin` role only
- **mTLS:** Internal service-to-service calls (Celery workers → orchestrator) use mutual TLS

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `ApplicationNotFoundError` | 404 | ORCH_001 | "Application {id} not found" | Invalid UUID or no DB match |
| `ValidationError` | 422 | ORCH_002 | "{field}: {reason}" | Pydantic validation failure |
| `BusinessRuleViolationError` | 409 | ORCH_003 | "Rule {rule} violated: {detail}" | GDS/TDS limits exceeded, invalid state transition |
| `InvalidFinancialDataError` | 400 | ORCH_004 | "Financial constraint violated: {detail}" | mortgage_amount > purchase_price |
| `FintracThresholdError` | 422 | ORCH_005 | "Transaction amount {amount} below FINTRAC threshold" | Report attempt for < $10,000 |
| `ClientRiskProfileNotFoundError` | 404 | ORCH_006 | "Risk profile for client {client_id} not found" | No FINTRAC history |
| `ProcessingTimeoutError` | 504 | ORCH_007 | "Task {task_id} timed out after {seconds}s" | Celery task exceeds timeout |
| `DocumentIntegrityError` | 409 | ORCH_008 | "Document checksum mismatch: {s3_key}" | Document tampering detected |
| `ReprocessNotAllowedError` | 409 | ORCH_009 | "Application {id} cannot be reprocessed (status: {status})" | Status not in ['exception', 'decided'] |
| `EncryptionKeyUnavailableError` | 500 | ORCH_010 | "KMS unavailable for PII encryption" | KMS service down |

**Error Response Format (Consistent across all endpoints):**
```json
{
  "detail": "Application 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "ORCH_001",
  "correlation_id": "corr-1234567890",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

**Retry Mechanisms:**
- Celery tasks: Exponential backoff (2^retry_count seconds) with max retries as specified
- Database connections: 3 retries with jitter via `common/database.py`
- External service calls (MinIO, KMS): Circuit breaker pattern after 5 failures

**Timeout Configurations:**
- `extract_documents`: 5 min per document
- `evaluate_policy`: 3 min
- `run_decision`: 2 min
- API endpoints: 30s default (configurable via `common/config.py`)
- Database queries: 10s statement timeout

**Health Check Endpoints:**
- `GET /health`: Returns 200 if API responsive
- `GET /health/celery`: Checks Celery worker connectivity
- `GET /health/db`: Database connectivity test
- `GET /health/minio`: S3 storage connectivity test

**Observability Integration:**
- All endpoints emit OpenTelemetry spans
- Prometheus metrics: `orchestrator_applications_total`, `orchestrator_processing_duration_seconds`, `orchestrator_fintrac_reports_filed_total`
- Structured JSON logs with `correlation_id` propagated from `X-Correlation-ID` header
```