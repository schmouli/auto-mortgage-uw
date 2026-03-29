# Design: Frontend React UI
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Frontend UI Module Design Plan

**Design Document:** `docs/design/frontend_ui.md`  
**Module:** `frontend_ui`  
**Purpose:** Backend API support for React-based mortgage underwriting user interface

---

## 1. Endpoints

### 1.1 Document Management
**`POST /api/v1/documents/upload`**
- **Auth:** Authenticated (lender/underwriter roles)
- **Request:** `multipart/form-data`
  - `file`: PDF document (max 10MB)
  - `document_type`: enum (`pay_stub`, `tax_return`, `bank_statement`, `property_appraisal`, `id_verification`)
  - `application_id`: UUID (optional, for association)
- **Response:** `201 Created`
  ```json
  {
    "document_id": "uuid",
    "filename": "string",
    "document_type": "enum",
    "status": "uploaded|processing|failed",
    "uploaded_at": "datetime",
    "file_size_bytes": "integer",
    "checksum": "string"
  }
  ```
- **Errors:**
  - `400`: `DOCUMENT_001` - Invalid file type (non-PDF)
  - `400`: `DOCUMENT_002` - File size exceeds limit
  - `422`: `DOCUMENT_003` - Virus/malware detected
  - `401`: `AUTH_001` - Unauthorized

**`GET /api/v1/documents/{document_id}`**
- **Auth:** Authenticated
- **Response:** `200 OK` (metadata only, never return file content in JSON)
- **Errors:**
  - `404`: `DOCUMENT_004` - Document not found

### 1.2 Application Submission
**`POST /api/v1/applications`**
- **Auth:** Authenticated (lender role)
- **Request:** `ApplicationCreateSchema`
  ```json
  {
    "lender_id": "uuid",
    "borrower_profile_id": "uuid",
    "property_value": "Decimal(12,2)",
    "loan_amount": "Decimal(12,2)",
    "contract_rate": "Decimal(5,2)",
    "amortization_years": "integer",
    "document_ids": ["uuid"],
    "insurance_required": "boolean|null"
  }
  ```
- **Response:** `202 Accepted`
  ```json
  {
    "application_id": "uuid",
    "status": "submitted",
    "pipeline_stage": "extraction",
    "submitted_at": "datetime",
    "estimated_completion": "datetime"
  }
  ```
- **Errors:**
  - `409`: `APPLICATION_001` - Duplicate application detected
  - `422`: `APPLICATION_002` - LTV exceeds 95% (CMHC limit)
  - `422`: `APPLICATION_003` - Required documents missing

### 1.3 Application Status Tracking
**`GET /api/v1/applications/{application_id}/status`**
- **Auth:** Authenticated (owner or underwriter)
- **Response:** `200 OK`
  ```json
  {
    "application_id": "uuid",
    "status": "submitted|underwriting|approved|rejected|exception",
    "pipeline_stage": "extraction|policy_check|ratio_calculation|decision|final_review",
    "stage_progress_percent": "integer",
    "stage_started_at": "datetime",
    "stage_completed_at": "datetime|null",
    "current_task": "string",
    "estimated_completion": "datetime|null"
  }
  ```
- **Errors:**
  - `404`: `APPLICATION_004` - Application not found
  - `403`: `AUTH_002` - Access denied

**`GET /api/v1/applications/{application_id}/pipeline-events`**
- **Auth:** Authenticated
- **Response:** `200 OK`
  ```json
  {
    "events": [
      {
        "event_id": "uuid",
        "stage": "string",
        "status": "started|completed|failed",
        "timestamp": "datetime",
        "metadata": "json"
      }
    ]
  }
  ```

### 1.4 Decision Review
**`GET /api/v1/applications/{application_id}/decision`**
- **Auth:** Authenticated (owner or underwriter)
- **Response:** `200 OK`
  ```json
  {
    "decision_id": "uuid",
    "application_id": "uuid",
    "decision_status": "approved|rejected|refer_to_underwriter",
    "gds_ratio": "Decimal(5,2)",
    "tds_ratio": "Decimal(5,2)",
    "qualifying_rate": "Decimal(5,2)",
    "stress_test_applied": "boolean",
    "cmhc_insurance_required": "boolean",
    "cmhc_premium": "Decimal(12,2)|null",
    "premium_tier": "80.01-85|85.01-90|90.01-95|null",
    "flags": [
      {
        "flag_type": "high_ltv|low_credit|high_gds|high_tds|incomplete_documents",
        "severity": "low|medium|high|critical",
        "description": "string"
      }
    ],
    "ratio_breakdown": {
      "gross_monthly_income": "Decimal(12,2)",
      "principal": "Decimal(12,2)",
      "interest": "Decimal(12,2)",
      "taxes": "Decimal(12,2)",
      "heat": "Decimal(12,2)",
      "other_debt_payments": "Decimal(12,2)"
    },
    "decisioned_at": "datetime",
    "decisioned_by": "uuid|null"
  }
  ```
- **Errors:**
  - `404`: `DECISION_001` - Decision not found
  - `409`: `DECISION_002` - Decision not yet available

### 1.5 Audit Trail Viewer
**`GET /api/v1/applications/{application_id}/audit-trail`**
- **Auth:** Authenticated (must have audit_view permission)
- **Response:** `200 OK`
  ```json
  {
    "audit_entries": [
      {
        "entry_id": "uuid",
        "action": "submitted|document_uploaded|status_changed|decision_made|flag_raised",
        "actor_id": "uuid",
        "actor_type": "lender|underwriter|system",
        "timestamp": "datetime",
        "ip_address": "string",
        "user_agent": "string",
        "details": "json",
        "retention_until": "datetime"
      }
    ]
  }
  ```
- **Security:** Never include SIN, DOB, or income values in details field

### 1.6 Exception Queue Management
**`GET /api/v1/exception-queue`**
- **Auth:** Authenticated (underwriter role)
- **Query Params:** `status=open|pending_review|resolved`, `severity=high|critical`, `sort_by=created_at|priority`, `page=1`, `limit=50`
- **Response:** `200 OK`
  ```json
  {
    "total_count": "integer",
    "page": "integer",
    "items": [
      {
        "exception_id": "uuid",
        "application_id": "uuid",
        "borrower_hash": "string", // SHA256 of SIN for lookup only
        "flags": ["string"],
        "severity": "string",
        "status": "string",
        "assigned_underwriter_id": "uuid|null",
        "created_at": "datetime",
        "days_in_queue": "integer"
      }
    ]
  }
  ```

**`POST /api/v1/exception-queue/{exception_id}/assign`**
- **Auth:** Underwriter role
- **Request:** `{"underwriter_id": "uuid"}`
- **Response:** `200 OK`

**`POST /api/v1/exception-queue/{exception_id}/resolve`**
- **Auth:** Underwriter role
- **Request:** `{"resolution": "approved|rejected", "notes": "string"}`
- **Response:** `200 OK`

---

## 2. Models & Database

### 2.1 `document_uploads` Table
```python
class DocumentUpload(Base):
    __tablename__ = "document_uploads"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), index=True)
    lender_id: Mapped[UUID] = mapped_column(ForeignKey("lenders.id"))
    
    filename: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[Enum] = mapped_column(SQLAlchemyEnum(DocumentType))
    content_type: Mapped[str] = mapped_column(String(100))  # application/pdf only
    
    # File storage metadata
    file_size_bytes: Mapped[int]
    checksum_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    storage_path: Mapped[str] = mapped_column(String(500))  # Encrypted path, not direct URL
    
    # Processing status
    status: Mapped[Enum] = mapped_column(SQLAlchemyEnum(DocumentStatus), default="uploaded")
    processing_error: Mapped[str|None] = mapped_column(Text)
    
    # FINTRAC compliance
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    ip_address: Mapped[str|None] = mapped_column(String(45))  # IPv6 support
    user_agent: Mapped[str|None] = mapped_column(Text)
    
    # Index for compliance queries
    __table_args__ = (
        Index("idx_documents_lender_created", "lender_id", "created_at"),
        Index("idx_documents_checksum", "checksum_sha256"),
        CheckConstraint("content_type = 'application/pdf'", name="chk_pdf_only"),
        CheckConstraint("file_size_bytes <= 10485760", name="chk_file_size_limit")
    )
```

### 2.2 `application_pipeline_status` Table
```python
class ApplicationPipelineStatus(Base):
    __tablename__ = "application_pipeline_status"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), unique=True, index=True)
    
    # Current state
    status: Mapped[Enum] = mapped_column(SQLAlchemyEnum(ApplicationStatus))
    pipeline_stage: Mapped[Enum] = mapped_column(SQLAlchemyEnum(PipelineStage))
    stage_progress_percent: Mapped[int] = mapped_column(default=0)
    
    # Timing
    stage_started_at: Mapped[datetime] = mapped_column(DateTime)
    stage_completed_at: Mapped[datetime|None] = mapped_column(DateTime)
    estimated_completion: Mapped[datetime|None] = mapped_column(DateTime)
    
    # Current task description (for UI)
    current_task: Mapped[str|None] = mapped_column(String(200))
    
    # Retry tracking
    retry_count: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str|None] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_pipeline_status_stage", "pipeline_stage", "status"),
        Index("idx_pipeline_estimated_completion", "estimated_completion"),
    )
```

### 2.3 `underwriting_decisions` Table
```python
class UnderwritingDecision(Base):
    __tablename__ = "underwriting_decisions"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), unique=True, index=True)
    
    # Decision outcome
    decision_status: Mapped[Enum] = mapped_column(SQLAlchemyEnum(DecisionStatus))
    decisioned_at: Mapped[datetime] = mapped_column(DateTime)
    decisioned_by: Mapped[UUID|None] = mapped_column(ForeignKey("users.id"))  # Null for automated decisions
    
    # OSFI B-20 Ratios (Decimal for precision)
    gds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    tds_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    qualifying_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))  # max(contract_rate + 2%, 5.25%)
    stress_test_applied: Mapped[bool] = mapped_column(default=True)
    
    # CMHC Insurance
    cmhc_insurance_required: Mapped[bool]
    cmhc_premium: Mapped[Decimal|None] = mapped_column(Numeric(12, 2))
    premium_tier: Mapped[Enum|None] = mapped_column(SQLAlchemyEnum(PremiumTier))
    
    # Ratio breakdown (stored as JSON for audit)
    ratio_breakdown: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Flags raised during underwriting
    flags: Mapped[list[dict]] = mapped_column(JSON, default=list)
    
    # Immutable audit trail
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    
    # 5-year retention marker (FINTRAC)
    retention_until: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=1825))
    
    __table_args__ = (
        Index("idx_decision_status", "decision_status"),
        Index("idx_decision_retention", "retention_until"),
        CheckConstraint("gds_ratio <= 39.0", name="chk_gds_limit"),
        CheckConstraint("tds_ratio <= 44.0", name="chk_tds_limit"),
    )
```

### 2.4 `exception_queue` Table
```python
class ExceptionQueue(Base):
    __tablename__ = "exception_queue"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id"), unique=True, index=True)
    
    # Borrower identifier (hashed SIN for FINTRAC compliance)
    borrower_sin_hash: Mapped[str] = mapped_column(String(64), index=True)
    
    # Exception details
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)  # Array of flag types
    severity: Mapped[Enum] = mapped_column(SQLAlchemyEnum(ExceptionSeverity))
    status: Mapped[Enum] = mapped_column(SQLAlchemyEnum(ExceptionStatus), default="open")
    
    # Assignment
    assigned_underwriter_id: Mapped[UUID|None] = mapped_column(ForeignKey("users.id"), index=True)
    
    # Resolution tracking
    resolution: Mapped[Enum|None] = mapped_column(SQLAlchemyEnum(ExceptionResolution))
    resolution_notes: Mapped[str|None] = mapped_column(Text)
    resolved_at: Mapped[datetime|None] = mapped_column(DateTime)
    resolved_by: Mapped[UUID|None] = mapped_column(ForeignKey("users.id"))
    
    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # FINTRAC: Track days in queue for reporting
    days_in_queue: Mapped[int] = mapped_column(default=0)
    
    __table_args__ = (
        Index("idx_exception_assigned_status", "assigned_underwriter_id", "status"),
        Index("idx_exception_severity", "severity", "created_at"),
    )
```

---

## 3. Business Logic

### 3.1 Document Upload Validation
- **File Type:** Strict MIME type validation for `application/pdf`
- **Size Limit:** 10MB per file (configurable via `common/config.py`)
- **Virus Scan:** Integration with ClamAV via `uv run clamav-async` before saving
- **Checksum:** SHA-256 calculated for deduplication and integrity verification
- **Encryption:** Files encrypted with AES-256 before storage (S3-compatible backend)
- **PIPEDA:** Never log filename if it contains SIN or DOB; sanitize metadata

### 3.2 Pipeline Stage Progress Calculation
```python
# Stage duration estimates (hours)
STAGE_ESTIMATES = {
    "extraction": 2,
    "policy_check": 1,
    "ratio_calculation": 1,
    "decision": 0.5,
    "final_review": 4
}

def calculate_progress(current_stage: str, stage_start: datetime) -> int:
    """
    Calculate progress percentage for UI progress bar
    """
    elapsed = (datetime.utcnow() - stage_start).total_seconds() / 3600
    estimate = STAGE_ESTIMATES.get(current_stage, 1)
    
    # Cap at 95% until manual completion signal
    progress = min(int((elapsed / estimate) * 100), 95)
    return progress
```

### 3.3 OSFI B-20 Ratio Calculation (Auditable)
```python
def calculate_gds_tds(
    loan_amount: Decimal,
    property_value: Decimal,
    contract_rate: Decimal,
    amortization_years: int,
    gross_annual_income: Decimal,
    annual_taxes: Decimal,
    annual_heat: Decimal,
    other_debt_payments: Decimal
) -> dict:
    """
    Returns auditable breakdown for UI display
    """
    # Stress test rate
    qualifying_rate = max(contract_rate + Decimal("2.0"), Decimal("5.25"))
    
    # Monthly amounts
    monthly_rate = qualifying_rate / 12 / 100
    num_payments = amortization_years * 12
    
    # Mortgage payment (P+I)
    principal_interest = loan_amount * (
        monthly_rate * (1 + monthly_rate) ** num_payments
    ) / ((1 + monthly_rate) ** num_payments - 1)
    
    monthly_taxes = annual_taxes / 12
    monthly_heat = annual_heat / 12
    gross_monthly_income = gross_annual_income / 12
    
    # GDS = (PITH) / Gross Monthly Income
    gds = ((principal_interest + monthly_taxes + monthly_heat) / gross_monthly_income) * 100
    
    # TDS = (PITH + Other Debt) / Gross Monthly Income
    tds = ((principal_interest + monthly_taxes + monthly_heat + other_debt_payments) / gross_monthly_income) * 100
    
    # Log full breakdown for audit (structlog)
    logger.info(
        "ratio_calculated",
        application_id=application_id,
        qualifying_rate=str(qualifying_rate),
        gds=str(round(gds, 2)),
        tds=str(round(tds, 2)),
        breakdown={
            "principal_interest": str(principal_interest),
            "monthly_taxes": str(monthly_taxes),
            "monthly_heat": str(monthly_heat),
            "gross_monthly_income": str(gross_monthly_income),
            "other_debt_payments": str(other_debt_payments)
        }
    )
    
    return {
        "gds_ratio": round(gds, 2),
        "tds_ratio": round(tds, 2),
        "qualifying_rate": qualifying_rate,
        "breakdown": {
            "principal_interest": principal_interest,
            "monthly_taxes": monthly_taxes,
            "monthly_heat": monthly_heat,
            "gross_monthly_income": gross_monthly_income,
            "other_debt_payments": other_debt_payments
        }
    }
```

**Hard Limits:** GDS > 39% or TDS > 44% → automatic rejection with `refer_to_underwriter` flag

### 3.4 Exception Queue Routing Logic
```python
def route_to_exception_queue(decision: UnderwritingDecision) -> bool:
    """
    Determines if application requires human review
    """
    flags = []
    
    # CMHC threshold
    ltv = decision.loan_amount / decision.property_value * 100
    if ltv > Decimal("80"):
        flags.append("high_ltv")
    
    # Ratio thresholds
    if decision.gds_ratio > Decimal("35"):
        flags.append("high_gds")
    if decision.tds_ratio > Decimal("40"):
        flags.append("high_tds")
    
    # Credit score (from external service)
    if decision.credit_score < 650:
        flags.append("low_credit")
    
    # Document completeness
    if len(decision.documents) < 3:
        flags.append("incomplete_documents")
    
    # FINTRAC: Transaction > $10,000 requires flag
    if decision.loan_amount > Decimal("10000"):
        flags.append("large_transaction")
    
    if flags:
        create_exception_entry(
            application_id=decision.application_id,
            flags=flags,
            severity=calculate_severity(flags, decision),
            borrower_sin_hash=hash_sin(decision.sin)  # PIPEDA: hash only
        )
        return True
    
    return False
```

### 3.5 Audit Trail Immutability
- All `POST/PUT/DELETE` operations create new audit entries
- `updated_at` timestamps trigger audit log writes
- No physical deletion: all records marked `retention_until` + 5 years
- FINTRAC compliance: `ip_address` and `user_agent` captured for all mutations

---

## 4. Migrations

### 4.1 New Tables
```sql
-- Create document_uploads table
CREATE TABLE document_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID REFERENCES applications(id),
    lender_id UUID REFERENCES lenders(id),
    filename VARCHAR(255) NOT NULL,
    document_type document_type_enum NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    checksum_sha256 VARCHAR(64) UNIQUE NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    status document_status_enum DEFAULT 'uploaded',
    processing_error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX idx_documents_lender_created ON document_uploads(lender_id, created_at);
CREATE INDEX idx_documents_checksum ON document_uploads(checksum_sha256);
CREATE INDEX idx_documents_application ON document_uploads(application_id);

-- Create application_pipeline_status table
CREATE TABLE application_pipeline_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID UNIQUE REFERENCES applications(id),
    status application_status_enum NOT NULL,
    pipeline_stage pipeline_stage_enum NOT NULL,
    stage_progress_percent INTEGER DEFAULT 0,
    stage_started_at TIMESTAMP NOT NULL,
    stage_completed_at TIMESTAMP,
    estimated_completion TIMESTAMP,
    current_task VARCHAR(200),
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pipeline_status_stage ON application_pipeline_status(pipeline_stage, status);
CREATE INDEX idx_pipeline_estimated_completion ON application_pipeline_status(estimated_completion);

-- Create underwriting_decisions table
CREATE TABLE underwriting_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID UNIQUE REFERENCES applications(id),
    decision_status decision_status_enum NOT NULL,
    decisioned_at TIMESTAMP NOT NULL,
    decisioned_by UUID REFERENCES users(id),
    gds_ratio NUMERIC(5,2) NOT NULL,
    tds_ratio NUMERIC(5,2) NOT NULL,
    qualifying_rate NUMERIC(5,2) NOT NULL,
    stress_test_applied BOOLEAN DEFAULT TRUE,
    cmhc_insurance_required BOOLEAN NOT NULL,
    cmhc_premium NUMERIC(12,2),
    premium_tier premium_tier_enum,
    ratio_breakdown JSON NOT NULL,
    flags JSON DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    retention_until TIMESTAMP NOT NULL DEFAULT NOW() + INTERVAL '5 years'
);

CREATE INDEX idx_decision_status ON underwriting_decisions(decision_status);
CREATE INDEX idx_decision_retention ON underwriting_decisions(retention_until);

-- Create exception_queue table
CREATE TABLE exception_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID UNIQUE REFERENCES applications(id),
    borrower_sin_hash VARCHAR(64) NOT NULL,
    flags JSON DEFAULT '[]',
    severity exception_severity_enum NOT NULL,
    status exception_status_enum DEFAULT 'open',
    assigned_underwriter_id UUID REFERENCES users(id),
    resolution exception_resolution_enum,
    resolution_notes TEXT,
    resolved_at TIMESTAMP,
    resolved_by UUID REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    days_in_queue INTEGER DEFAULT 0
);

CREATE INDEX idx_exception_assigned_status ON exception_queue(assigned_underwriter_id, status);
CREATE INDEX idx_exception_sin_hash ON exception_queue(borrower_sin_hash);
CREATE INDEX idx_exception_severity ON exception_queue(severity, created_at);
```

### 4.2 New Enum Types
```sql
CREATE TYPE document_type_enum AS ENUM (
    'pay_stub', 'tax_return', 'bank_statement', 
    'property_appraisal', 'id_verification'
);

CREATE TYPE document_status_enum AS ENUM (
    'uploaded', 'processing', 'completed', 'failed'
);

CREATE TYPE pipeline_stage_enum AS ENUM (
    'extraction', 'policy_check', 'ratio_calculation', 
    'decision', 'final_review'
);

CREATE TYPE decision_status_enum AS ENUM (
    'approved', 'rejected', 'refer_to_underwriter'
);

CREATE TYPE premium_tier_enum AS ENUM (
    '80.01-85', '85.01-90', '90.01-95'
);

CREATE TYPE exception_severity_enum AS ENUM (
    'low', 'medium', 'high', 'critical'
);

CREATE TYPE exception_status_enum AS ENUM (
    'open', 'pending_review', 'resolved'
);

CREATE TYPE exception_resolution_enum AS ENUM (
    'approved', 'rejected', 'escalated'
);
```

### 4.3 Existing Table Modifications
```sql
-- Add pipeline tracking to applications table
ALTER TABLE applications 
ADD COLUMN IF NOT EXISTS current_pipeline_stage pipeline_stage_enum,
ADD COLUMN IF NOT EXISTS pipeline_status_id UUID REFERENCES application_pipeline_status(id);
```

---

## 5. Security & Compliance

### 5.1 OSFI B-20 Requirements
- **Stress Test:** All ratio calculations MUST use `qualifying_rate = max(contract_rate + 2%, 5.25%)` - enforced in `services.py` with database CHECK constraint
- **Hard Limits:** GDS ≤ 39%, TDS ≤ 44% - violations automatically reject and route to exception queue
- **Auditability:** Every ratio calculation logged with full breakdown (principal, interest, taxes, heat, income) - stored in `underwriting_decisions.ratio_breakdown` JSON field
- **Immutability:** Decision records never updated; new decisions create new rows for re-evaluation tracking

### 5.2 FINTRAC Compliance
- **Large Transactions:** Loan amount > CAD $10,000 automatically flagged (`large_transaction` flag)
- **5-Year Retention:** All records have `retention_until` timestamp; archive job runs monthly
- **Immutable Records:** No UPDATE/DELETE on critical tables; all changes append-only with audit trail
- **Identity Verification:** Document uploads of type `id_verification` trigger enhanced logging
- **Reporting Trigger:** Exception queue entries with `large_transaction` flag generate daily report for compliance team

### 5.3 CMHC Insurance Logic
```python
# LTV calculation with Decimal precision
ltv = loan_amount / property_value * 100

if ltv > Decimal("80"):
    insurance_required = True
    if Decimal("80.01") <= ltv <= Decimal("85.00"):
        premium_rate = Decimal("0.0280")
        tier = "80.01-85"
    elif Decimal("85.01") <= ltv <= Decimal("90.00"):
        premium_rate = Decimal("0.0310")
        tier = "85.01-90"
    elif Decimal("90.01") <= ltv <= Decimal("95.00"):
        premium_rate = Decimal("0.0400")
        tier = "90.01-95"
    else:
        raise ValueError("LTV exceeds CMHC maximum")
    
    premium = loan_amount * premium_rate
else:
    insurance_required = False
```

### 5.4 PIPEDA Data Handling
- **Encryption at Rest:** 
  - Document files: AES-256 encryption in storage (S3 bucket with SSE-KMS)
  - SIN/DOB: Never stored in frontend-related tables; only hashed `borrower_sin_hash` for lookups
- **Data Minimization:** Frontend APIs only return fields necessary for UI display; full PII restricted to `borrower_profiles` module
- **No Logging:** Middleware filters SIN, DOB, income, banking data from all logs and error messages
- **Secure File Access:** Document download endpoints return pre-signed URLs (15-minute expiry) instead of direct file content

### 5.5 Authentication & Authorization
```python
# Role-based access control
REQUIRED_PERMISSIONS = {
    "POST /api/v1/documents/upload": ["lender", "underwriter"],
    "GET /api/v1/applications/{id}/status": ["owner", "underwriter"],
    "GET /api/v1/applications/{id}/decision": ["owner", "underwriter"],
    "GET /api/v1/applications/{id}/audit-trail": ["audit_viewer", "admin"],
    "GET /api/v1/exception-queue": ["underwriter"],
    "POST /api/v1/exception-queue/{id}/assign": ["underwriter"],
    "POST /api/v1/exception-queue/{id}/resolve": ["underwriter"]
}
```

---

## 6. Error Codes & HTTP Responses

### 6.1 Document Module Errors
| Exception Class | HTTP Status | Error Code | Message Pattern | Compliance Note |
|-----------------|-------------|------------|-----------------|-----------------|
| `DocumentUploadError` | 400 | `DOCUMENT_001` | "Invalid file type: {mime_type}. Only PDF allowed" | PIPEDA: Don't log filename |
| `DocumentSizeExceededError` | 413 | `DOCUMENT_002` | "File size {size}MB exceeds limit of 10MB" | - |
| `DocumentVirusDetectedError` | 422 | `DOCUMENT_003` | "Malware detected in upload" | FINTRAC: Log hash only |
| `DocumentNotFoundError` | 404 | `DOCUMENT_004` | "Document {document_id} not found" | - |

### 6.2 Application Module Errors
| Exception Class | HTTP Status | Error Code | Message Pattern | Compliance Note |
|-----------------|-------------|------------|-----------------|-----------------|
| `DuplicateApplicationError` | 409 | `APPLICATION_001` | "Application already exists for borrower {hash}" | PIPEDA: Use SIN hash |
| `LTVLimitExceededError` | 422 | `APPLICATION_002` | "LTV {ltv}% exceeds CMHC maximum of 95%" | CMHC requirement |
| `MissingDocumentsError` | 422 | `APPLICATION_003` | "Required documents missing: {doc_types}" | - |
| `ApplicationNotFoundError` | 404 | `APPLICATION_004` | "Application {id} not found" | - |

### 6.3 Decision Module Errors
| Exception Class | HTTP Status | Error Code | Message Pattern | Compliance Note |
|-----------------|-------------|------------|-----------------|-----------------|
| `DecisionNotFoundError` | 404 | `DECISION_001` | "Decision for application {id} not found" | - |
| `DecisionNotReadyError` | 409 | `DECISION_002` | "Decision not yet calculated (stage: {stage})" | - |
| `RatioLimitViolationError` | 422 | `DECISION_003` | "OSFI B-20 limit violated: GDS {gds}% > 39% or TDS {tds}% > 44%" | OSFI compliance |

### 6.4 Exception Queue Errors
| Exception Class | HTTP Status | Error Code | Message Pattern | Compliance Note |
|-----------------|-------------|------------|-----------------|-----------------|
| `ExceptionNotFoundError` | 404 | `EXCEPTION_001` | "Exception {id} not found in queue" | - |
| `ExceptionAlreadyAssignedError` | 409 | `EXCEPTION_002` | "Exception already assigned to {underwriter}" | - |
| `UnauthorizedResolutionError` | 403 | `EXCEPTION_003` | "Only assigned underwriter can resolve" | RBAC enforcement |

### 6.5 Global Security Errors
| Exception Class | HTTP Status | Error Code | Message Pattern |
|-----------------|-------------|------------|-----------------|
| `UnauthorizedError` | 401 | `AUTH_001` | "Invalid or missing authentication token" |
| `AccessDeniedError` | 403 | `AUTH_002` | "Insufficient permissions for resource" |

---

## 7. Frontend Integration Considerations

### 7.1 API Response Optimization
- **Pagination:** All list endpoints support `page` and `limit` (max 100)
- **Field Filtering:** Use `?fields=gds_ratio,tds_ratio` to minimize payload
- **ETag Caching:** Decision and status endpoints return ETags for 304 responses
- **WebSocket Updates:** `/ws/applications/{id}/status` for real-time pipeline progress

### 7.2 Performance & Scalability
- **Database:** All tables have composite indexes for common filter combinations
- **Rate Limiting:** Document uploads limited to 10/minute per user (Redis-backed)
- **Async Processing:** Document OCR/extraction handled by Celery workers; status polled via API
- **CDN:** Pre-signed document URLs point to CloudFront with 1-hour TTL

### 7.3 Observability
- **Traces:** All endpoints emit OpenTelemetry spans with `correlation_id`
- **Metrics:** Prometheus counters for `document_uploads_total`, `pipeline_stage_duration_seconds`, `exception_queue_size`
- **Logging:** structlog JSON with `module=frontend_ui`, `user_id`, `ip_address` (never PII)

---

**Warning:** This design plan focuses on backend APIs required to support the React frontend. Frontend-specific concerns (WCAG 2.1, i18n, responsive design, component architecture) should be documented in a separate `docs/design/frontend_ui_react.md` file by a frontend specialist.