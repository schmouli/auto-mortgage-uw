# Design: Orchestrator Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

```markdown
# Orchestrator Service Design Plan

**Module:** `orchestrator`  
**Feature Slug:** `orchestrator-service`  
**Document:** `docs/design/orchestrator-service.md`

---

## 1. Endpoints

### Application Management

#### `POST /api/v1/applications`
Submit a new mortgage application and trigger pipeline.

**Auth:** Authenticated (lender user)  
**Request Schema (`ApplicationCreateSchema`):**
```python
{
  "borrower": {
    "full_name": str,  # Required, max 255 chars
    "sin": str,  # Required, 9 digits, encrypted at rest
    "date_of_birth": date,  # Required, encrypted at rest
    "employment_type": Literal["salaried", "self-employed", "contract"],  # Required
    "gross_annual_income": Decimal,  # Required, > 0, max 12 digits
    "credit_score": int,  # Required, 300-900
    "address": {
      "street": str,  # Required, encrypted
      "city": str,  # Required
      "province": str,  # Required, 2-letter code
      "postal_code": str  # Required, encrypted
    }
  },
  "lender_id": UUID,  # Required
  "property_value": Decimal,  # Required, > 0, max 15 digits
  "purchase_price": Decimal,  # Required, > 0, max 15 digits
  "mortgage_amount": Decimal,  # Required, > 0, max 15 digits
  "documents": List[DocumentUploadSchema]  # Required, min 1 document
}
```

**Response Schema (`ApplicationSchema`):**
```python
{
  "id": UUID,
  "status": Literal["submitted", "extracting", "evaluating", "decided", "exception"],
  "borrower_id": UUID,
  "lender_id": UUID,
  "property_value": Decimal,
  "purchase_price": Decimal,
  "mortgage_amount": Decimal,
  "ltv_ratio": Decimal,
  "insurance_required": bool,
  "insurance_premium": Optional[Decimal],
  "decision_result": Optional[DecisionResultSchema],
  "created_at": datetime,
  "updated_at": datetime,
  "created_by": str
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 400 | `ORCHESTRATOR_003` | Document validation failed: {reason} |
| 422 | `ORCHESTRATOR_002` | Field validation error: {field} |
| 409 | `ORCHESTRATOR_007` | LTV exceeds maximum allowable threshold (95%) |
| 401 | `SECURITY_001` | Invalid or missing JWT token |

---

#### `GET /api/v1/applications/{id}`
Retrieve application status and decision details.

**Auth:** Authenticated (owning lender or admin)  
**Response Schema:** `ApplicationSchema` (PII fields excluded)  
**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 404 | `ORCHESTRATOR_001` | Application {id} not found |
| 403 | `SECURITY_002` | Access denied to application |

---

#### `GET /api/v1/applications/{id}/documents`
List uploaded documents with processing status.

**Auth:** Authenticated (owning lender)  
**Response Schema (`DocumentListSchema`):**
```python
{
  "application_id": UUID,
  "documents": List[{
    "id": UUID,
    "document_type": str,
    "filename": str,
    "status": Literal["uploaded", "processing", "extracted", "failed"],
    "created_at": datetime
  }]
}
```

---

#### `POST /api/v1/applications/{id}/reprocess`
Trigger reprocessing of an application in exception state.

**Auth:** Authenticated (admin or lender with permission)  
**Request Schema:** Optional `{"reason": str}`  
**Response Schema:** `{"id": UUID, "status": str, "reprocess_initiated_at": datetime}`  
**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 400 | `ORCHESTRATOR_006` | Reprocessing not allowed: current status is {status} |
| 404 | `ORCHESTRATOR_001` | Application not found |

---

#### `GET /api/v1/applications`
Paginated list of applications with filters.

**Auth:** Authenticated (lender sees own, admin sees all)  
**Query Parameters:**
- `page`: int (default 1)
- `page_size`: int (default 20, max 100)
- `status`: Optional[ApplicationStatusEnum]
- `lender_id`: Optional[UUID] (admin only filter)

**Response Schema (`PaginatedApplicationListSchema`):**
```python
{
  "items": List[ApplicationSchema],
  "total": int,
  "page": int,
  "page_size": int
}
```

---

### FINTRAC Compliance

#### `POST /api/v1/fintrac/applications/{id}/verify-identity`
Submit identity verification attempt.

**Auth:** Authenticated (lender user)  
**Request Schema (`IdentityVerificationSchema`):**
```python
{
  "verification_method": Literal["documentary", "electronic", "biometric"],
  "verification_data": Dict[str, Any]  # Method-specific data, no PII
}
```

**Response Schema:**
```python
{
  "verification_id": UUID,
  "status": Literal["pending", "verified", "failed"],
  "created_at": datetime
}
```

**Compliance:** Logs immutable audit record. Triggers FINTRAC Record Keeping Requirements.

---

#### `GET /api/v1/fintrac/applications/{id}/verification`
Get verification status.

**Auth:** Authenticated (owning lender)  
**Response Schema:** Identity verification record (PII excluded)  
**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 404 | `ORCHESTRATOR_004` | Verification record not found |

---

#### `POST /api/v1/fintrac/applications/{id}/report-transaction`
File FINTRAC transaction report for amounts > $10,000 CAD.

**Auth:** Authenticated (lender user)  
**Request Schema (`TransactionReportSchema`):**
```python
{
  "transaction_amount": Decimal,  # Required, > 10000.00
  "transaction_currency": str,  # Default "CAD"
  "transaction_type": str,  # Required, e.g., "mortgage_funding"
  "funding_source": str  # Required, e.g., "financial_institution"
}
```

**Response Schema:**
```python
{
  "report_id": UUID,
  "report_filed": bool,
  "filed_at": Optional[datetime]
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail |
|-------------|------------|--------|
| 422 | `ORCHESTRATOR_005` | Transaction amount ${amount} below FINTRAC threshold |
| 409 | `FINTRAC_001` | Report already filed for this application |

**Compliance:** Immutable record created. Filed reports cannot be modified (5-year retention).

---

#### `GET /api/v1/fintrac/risk-assessment/{client_id}`
Get aggregated risk assessment for a client across all applications.

**Auth:** Admin only  
**Response Schema (`RiskAssessmentSchema`):**
```python
{
  "client_id": UUID,
  "risk_score": Decimal,  # 0.0 to 1.0
  "risk_factors": List[str],
  "applications_reviewed": int,
  "last_updated": datetime
}
```

---

## 2. Models & Database

### `applications` Table
```python
class Application(Base):
    __tablename__ = "applications"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    borrower_id = Column(UUID, ForeignKey("borrowers.id"), nullable=False, index=True)
    lender_id = Column(String(255), nullable=False, index=True)  # From auth token
    
    # CMHC & Underwriting Fields
    property_value = Column(Numeric(15, 2), nullable=False)
    purchase_price = Column(Numeric(15, 2), nullable=False)
    mortgage_amount = Column(Numeric(15, 2), nullable=False)
    ltv_ratio = Column(Numeric(5, 4), nullable=False)  # Calculated: loan / value * 100
    
    # CMHC Insurance
    insurance_required = Column(Boolean, nullable=False, default=False)
    insurance_premium = Column(Numeric(15, 2), nullable=True)  # Populated if LTV > 80%
    
    # Pipeline Status
    status = Column(
        Enum("submitted", "extracting", "evaluating", "decided", "exception", 
             name="application_status"),
        nullable=False,
        index=True
    )
    
    # Decision Storage (OSFI Audit Trail)
    decision_result = Column(JSONB, nullable=True)  # Stores GDS/TDS breakdown, stress test rate, decision
    
    # FINTRAC Flag
    fintrac_report_required = Column(Boolean, nullable=False, default=False)
    
    # Audit Fields (FINTRAC 5-year retention)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, onupdate=func.now())
    created_by = Column(String(255), nullable=False)  # User ID from JWT
    
    # Relationships
    borrower = relationship("Borrower", back_populates="applications")
    documents = relationship("ApplicationDocument", back_populates="application")
    fintrac_verification = relationship("FintracVerification", uselist=False, back_populates="application")
    transaction_reports = relationship("FintracTransactionReport", back_populates="application")
    
    # Indexes
    __table_args__ = (
        Index("idx_applications_status_created", "status", "created_at"),
        Index("idx_applications_lender_status", "lender_id", "status"),
        CheckConstraint("ltv_ratio <= 95.00", name="ck_max_ltv_threshold"),
        CheckConstraint("mortgage_amount > 0", name="ck_positive_mortgage"),
    )
```

### `borrowers` Table
```python
class Borrower(Base):
    __tablename__ = "borrowers"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    full_name = Column(String(255), nullable=False)
    
    # PIPEDA: SIN encrypted, hash for lookups
    sin_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA256 hex digest
    sin_encrypted = Column(LargeBinary, nullable=False)  # AES-256 encrypted
    
    # PIPEDA: DOB encrypted
    date_of_birth_encrypted = Column(LargeBinary, nullable=False)
    
    employment_type = Column(
        Enum("salaried", "self-employed", "contract", name="employment_type_enum"),
        nullable=False,
        index=True
    )
    
    # Financial data (Decimal per project rules)
    gross_annual_income = Column(Numeric(12, 2), nullable=False)
    credit_score = Column(Integer, nullable=False)  # 300-900 range
    
    # Address (PIPEDA: encrypt street and postal code)
    address_street_encrypted = Column(LargeBinary, nullable=False)
    address_city = Column(String(100), nullable=False)
    address_province = Column(String(2), nullable=False)
    address_postal_code_encrypted = Column(LargeBinary, nullable=False)
    
    # Audit (Immutable per FINTRAC)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, onupdate=func.now())
    created_by = Column(String(255), nullable=False)
    
    # Relationships
    applications = relationship("Application", back_populates="borrower")
    
    __table_args__ = (
        CheckConstraint("credit_score BETWEEN 300 AND 900", name="ck_valid_credit_score"),
        CheckConstraint("gross_annual_income > 0", name="ck_positive_income"),
    )
```

### `application_documents` Table
```python
class ApplicationDocument(Base):
    __tablename__ = "application_documents"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    application_id = Column(UUID, ForeignKey("applications.id"), nullable=False, index=True)
    document_type = Column(
        Enum("paystub", "t4", "notice_assessment", "bank_statement", 
             "purchase_agreement", "identification", "employment_letter",
             name="document_type_enum"),
        nullable=False
    )
    filename = Column(String(500), nullable=False)
    s3_key = Column(String(1000), nullable=False, unique=True)  # MinIO/S3 path
    status = Column(
        Enum("uploaded", "processing", "extracted", "failed", name="doc_status_enum"),
        nullable=False,
        index=True
    )
    extraction_result = Column(JSONB, nullable=True)  # Data extracted from document
    
    # Audit
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, onupdate=func.now())
    
    # Relationships
    application = relationship("Application", back_populates="documents")
    
    __table_args__ = (
        Index("idx_docs_app_type", "application_id", "document_type"),
    )
```

### `fintrac_identity_verifications` Table
```python
class FintracVerification(Base):
    __tablename__ = "fintrac_identity_verifications"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    application_id = Column(UUID, ForeignKey("applications.id"), nullable=False, unique=True)
    
    # Verification method per FINTRAC guidelines
    verification_method = Column(
        Enum("documentary", "electronic", "biometric", name="verification_method_enum"),
        nullable=False
    )
    
    # Status tracking
    status = Column(
        Enum("pending", "verified", "failed", name="verification_status_enum"),
        nullable=False,
        index=True
    )
    
    verified_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Audit data (no PII)
    verification_metadata = Column(JSONB, nullable=False)  # Stores method-specific non-PII data
    
    # Immutable audit trail
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, onupdate=func.now())
    created_by = Column(String(255), nullable=False)
    
    # Relationships
    application = relationship("Application", back_populates="fintrac_verification")
```

### `fintrac_transaction_reports` Table
```python
class FintracTransactionReport(Base):
    __tablename__ = "fintrac_transaction_reports"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    application_id = Column(UUID, ForeignKey("applications.id"), nullable=False, index=True)
    
    # Transaction details (FINTRAC threshold: > $10,000 CAD)
    transaction_amount = Column(Numeric(15, 2), nullable=False)
    transaction_currency = Column(String(3), nullable=False, default="CAD")
    transaction_type = Column(String(100), nullable=False)  # e.g., "mortgage_disbursement"
    
    # Reporting status (Immutable once filed)
    report_filed = Column(Boolean, nullable=False, default=False)
    filed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    fintrac_reference_number = Column(String(50), nullable=True)  # FINTRAC acknowledgment
    
    # Audit (5-year retention)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(String(255), nullable=False)
    
    # Relationships
    application = relationship("Application", back_populates="transaction_reports")
    
    __table_args__ = (
        CheckConstraint("transaction_amount >= 10000.00", name="ck_fintrac_threshold"),
        Index("idx_reports_unfiled", "report_filed", "created_at"),
    )
```

---

## 3. Business Logic

### Pipeline Orchestration State Machine

```python
# State transitions are validated in services.py
STATE_TRANSITIONS = {
    "submitted": ["extracting", "exception"],
    "extracting": ["evaluating", "exception"],
    "evaluating": ["decided", "exception"],
    "decided": ["reprocess"],  # Only via admin action
    "exception": ["submitted"]  # Via reprocess endpoint
}
```

### Pipeline Flow Algorithm

1. **Application Submission (`POST /applications`)**
   - Validate input with Pydantic (strict mode)
   - Hash SIN using SHA256 for `sin_hash`
   - Encrypt SIN, DOB, street address, postal code using `encrypt_pii()`
   - Calculate LTV: `ltv_ratio = mortgage_amount / property_value * 100`
   - Determine CMHC insurance: if ltv_ratio > 80.00, set `insurance_required=True`
   - Calculate premium using tier lookup:
     - 80.01-85%: 2.80% of mortgage_amount
     - 85.01-90%: 3.10% of mortgage_amount
     - 90.01-95%: 4.00% of mortgage_amount
   - Set `fintrac_report_required = (mortgage_amount >= 10000.00)`
   - Create application record with status="submitted"
   - Upload documents to MinIO/S3 with key: `{lender_id}/{application_id}/{document_id}_{filename}`
   - Dispatch Celery chain: `extract_documents_task.s(application_id) | evaluate_policy_task.s() | run_decision_task.s()`
   - Return application ID and initial status

2. **Document Extraction Task (`extract_documents_task`)**
   - Timeout: 5 minutes, retries: 3 (exponential backoff: 2^retry * 60s)
   - Updates status to "extracting"
   - For each document: calls DocumentExtraction service (gRPC/HTTP)
   - Stores extraction_result JSON in application_documents table
   - On success: triggers next task
   - On failure: sets application status to "exception", logs error with correlation_id

3. **Policy Evaluation Task (`evaluate_policy_task`)**
   - Timeout: 3 minutes, retries: 2
   - Updates status to "evaluating"
   - Retrieves borrower data (income, credit score)
   - Calls Underwriting module to calculate:
     - GDS = (PITH + Insurance Premium) / gross_monthly_income
     - TDS = (PITH + Insurance Premium + Other Debts) / gross_monthly_income
     - **OSFI Stress Test:** qualifying_rate = max(contract_rate + 2%, 5.25%)
     - Recalculate GDS/TDS with stress test payment
     - Enforce hard limits: GDS ≤ 39%, TDS ≤ 44%
   - Stores calculation breakdown in `decision_result` JSON for audit
   - On validation failure: set status="exception" with decision_result containing rejection reason
   - On success: triggers decision task

4. **Decision Task (`run_decision_task`)**
   - Timeout: 2 minutes, no retries (idempotent)
   - Updates status to "decided"
   - Aggregates extraction results and policy evaluation
   - Stores final decision in `decision_result`:
     ```json
     {
       "decision": "approved"|"rejected"|"referred",
       "gds_ratio": 0.35,
       "tds_ratio": 0.42,
       "stress_test_rate": 5.25,
       "gds_under_stress": 0.38,
       "tds_under_stress": 0.43,
       "cmhc_insurance": {
         "required": true,
         "premium": 12400.00,
         "ltv": 85.50
       },
       "reasons": [...]
     }
   ```
   - If FINTRAC report required and not filed, create pending transaction_report record

5. **Reprocessing Logic (`POST /applications/{id}/reprocess`)**
   - Allowed only for status="exception" or admin override
   - Resets status to "submitted"
   - Clears previous decision_result but retains audit trail
   - Re-enqueues Celery pipeline
   - Logs reprocess reason with correlation_id

### FINTRAC Compliance Workflows

**Identity Verification:**
- Creates immutable `fintrac_identity_verifications` record
- `verification_metadata` stores non-PII: method, timestamp, verification provider, confidence score
- Status transitions: pending → verified/failed
- `verified_at` timestamp set on success
- Failed verifications require manual review before re-submission

**Transaction Reporting:**
- Automatic trigger when `mortgage_amount >= 10000.00`
- Creates `fintrac_transaction_reports` record with `report_filed=False`
- Separate Celery beat task polls unfiled reports and submits to FINTRAC API
- On successful FINTRAC acknowledgment, sets `report_filed=True` and stores reference number
- Records are immutable after filing (no updates allowed)

---

## 4. Migrations

### Alembic Revision: `create_orchestrator_tables`

**New Tables:**
1. `applications` - Main application orchestration table
2. `borrowers` - Borrower PII (encrypted) and financial data
3. `application_documents` - Document tracking and extraction results
4. `fintrac_identity_verifications` - FINTRAC identity verification audit trail
5. `fintrac_transaction_reports` - FINTRAC transaction reporting audit trail

**Indexes:**
- `idx_applications_status_created` (composite)
- `idx_applications_lender_status` (composite)
- `idx_borrowers_sin_hash` (unique)
- `idx_borrowers_credit_score`
- `idx_docs_app_type` (composite)
- `idx_reports_unfiled` (composite)

**Constraints:**
- `ck_max_ltv_threshold`: LTV ≤ 95%
- `ck_valid_credit_score`: 300-900 range
- `ck_fintrac_threshold`: transaction_amount ≥ 10000.00

**Data Migration:**
- None (new module)

---

## 5. Security & Compliance

### OSFI B-20 Implementation
- **Stress Test Enforcement:** The `evaluate_policy_task` must call Underwriting module with `qualifying_rate = max(contract_rate + 2%, 5.25%)` and recalculate ratios.
- **Hard Limits:** Underwriting module rejects applications where GDS > 39% or TDS > 44% under stress test. Decision result must include full calculation breakdown.
- **Audit Logging:** All ratio calculations logged with `correlation_id`, application_id, and timestamp for regulatory audit.

### FINTRAC Compliance
- **Immutable Records:** All `fintrac_*` tables have `created_at` but no updates permitted. Use database triggers to prevent UPDATE operations.
- **5-Year Retention:** PostgreSQL partition policy on `fintrac_transaction_reports` by year, retain 5 partitions (current + 4 previous).
- **Identity Verification:** Every `verify-identity` call creates permanent record. Log verification attempt with method and timestamp.
- **Transaction Reporting:** Automatic creation of report record for amounts ≥ $10,000 CAD. Separate async worker files report with FINTRAC. Report cannot be modified after filing.

### CMHC Insurance Logic
```python
def calculate_cmhc_premium(ltv: Decimal, mortgage_amount: Decimal) -> Decimal:
    if ltv <= 80.00:
        return Decimal("0.00")
    elif ltv <= 85.00:
        return mortgage_amount * Decimal("0.0280")
    elif ltv <= 90.00:
        return mortgage_amount * Decimal("0.0310")
    elif ltv <= 95.00:
        return mortgage_amount * Decimal("0.0400")
    else:
        raise ValueError("LTV exceeds 95% threshold")
```

### PIPEDA Data Handling
- **Encryption at Rest:** SIN, DOB, street address, postal_code encrypted with AES-256 via `encrypt_pii()` before storage.
- **Hash for Lookups:** SIN hashed with SHA256 for duplicate detection; hash is not reversible.
- **Data Minimization:** Only collect fields required for underwriting (no optional PII fields).
- **Logging:** NEVER log SIN, DOB, income, or banking data. Log only `application_id`, `borrower_id` hashes, and action types.

### Authentication & Authorization
- **JWT Bearer Token:** Required for all endpoints except health checks.
- **Scope-Based Access:**
  - `lender`: Can CRUD own applications, view own FINTRAC records
  - `fintrac_officer`: Can file transaction reports, view verifications
  - `admin`: Can reprocess any application, view all data, access risk assessment
- **mTLS:** Internal service-to-service communication (Celery workers, DocumentExtraction service) uses mutual TLS.

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `ApplicationNotFoundError` | 404 | `ORCHESTRATOR_001` | "Application {id} not found" | GET/POST on non-existent UUID |
| `InvalidApplicationStateError` | 409 | `ORCHESTRATOR_002` | "Invalid state transition: {from} → {to}" | Illegal status change |
| `DocumentUploadError` | 400 | `ORCHESTRATOR_003` | "Document upload failed: {detail}" | S3/MinIO failure, invalid format |
| `VerificationRecordNotFoundError` | 404 | `ORCHESTRATOR_004` | "Verification record for application {id} not found" | FINTRAC verification GET on missing record |
| `TransactionBelowThresholdError` | 422 | `ORCHESTRATOR_005` | "Transaction amount ${amount} below FINTRAC threshold" | Attempt to report < $10,000 |
| `ReprocessNotAllowedError` | 400 | `ORCHESTRATOR_006` | "Reprocessing not allowed: current status is {status}" | Reprocess on non-exception status |
| `LTVThresholdExceededError` | 409 | `ORCHESTRATOR_007` | "LTV {ltv}% exceeds maximum allowable 95%" | Application submission validation |
| `FINTRACReportAlreadyFiledError` | 409 | `FINTRAC_001` | "FINTRAC report already filed for application {id}" | Duplicate reporting attempt |

### Exception Handler Mapping
All exceptions inherit from `OrchestratorException(OrchestratorExceptionBase)` which extends `AppException` from `common.exceptions.py`. FastAPI exception handlers return structured JSON:

```json
{
  "detail": "Application 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "ORCHESTRATOR_001",
  "correlation_id": "correlation-id-from-request",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## 7. Additional Technical Specifications

### Celery Task Configuration
```python
# tasks.py
@celery.task(
    bind=True,
    max_retries=3,
    soft_time_limit=300,  # 5 min for extraction
    retry_backoff=True,
    retry_backoff_max=600,  # 10 min max
    retry_jitter=True
)
def extract_documents_task(self, application_id: UUID):
    ...
```

### Health Check Endpoints
- `GET /health/live` - Liveness probe (FastAPI uptime)
- `GET /health/ready` - Readiness probe (PostgreSQL + MinIO connectivity)
- `GET /health/celery` - Celery worker status

### Observability
- **Logging:** structlog JSON with correlation_id, user_id, application_id
- **Metrics:** Prometheus counters for `applications_submitted`, `applications_decided`, `fintrac_reports_filed`, `pipeline_exceptions`
- **Tracing:** OpenTelemetry spans for each Celery task and external service call

### Document Storage Security
- MinIO/S3 bucket policy: Private with pre-signed URLs (15-min expiry)
- Key structure: `{lender_id}/{application_id}/{document_id}_{secure_random}_{filename}`
- Server-side encryption enabled on bucket

### Timeout & Retry Configuration
| Operation | Timeout | Retries | Backoff |
|-----------|---------|---------|---------|
| Document Upload | 30s | 2 | Linear 2s |
| Document Extraction | 5 min | 3 | Exponential 2^retry * 60s |
| Policy Evaluation | 3 min | 2 | Exponential 2^retry * 30s |
| Decision Engine | 2 min | 0 | N/A |
| FINTRAC API Call | 10s | 5 | Exponential 2^retry * 5s |
```