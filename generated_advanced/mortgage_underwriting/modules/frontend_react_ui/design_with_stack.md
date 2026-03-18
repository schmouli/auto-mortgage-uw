# Design: Frontend React UI
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Frontend React UI Design Plan

**Feature Module:** `frontend-ui` (React Application)  
**Supporting Backend Module:** `applications`  
**Design Document:** `docs/design/frontend-ui.md`

---

## 1. Endpoints

The React UI consumes RESTful APIs from the backend `applications` module. All endpoints require JWT authentication via `Authorization: Bearer <token>` header.

### 1.1 Application Submission

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/applications` | Authenticated | Create new mortgage application |
| `POST` | `/api/v1/applications/{app_id}/documents` | Authenticated | Upload borrower PDF documents |
| `GET` | `/api/v1/lenders` | Authenticated | Fetch list of available lenders |

**Request: `POST /api/v1/applications`**
```typescript
interface CreateApplicationRequest {
  lender_id: string;              // UUID, required
  property_value: string;         // Decimal string, required
  loan_amount: string;            // Decimal string, required
  borrower_sin_hash: string;      // SHA256 hash for deduplication, required
  created_by: string;             // User ID from JWT, auto-populated
}
```

**Response: `201 Created`**
```typescript
interface ApplicationResponse {
  application_id: string;         // UUID
  status: "draft" | "submitted" | "extracting" | "underwriting" | "decision_ready" | "approved" | "rejected" | "exception";
  lender_id: string;
  property_value: string;         // Decimal
  loan_amount: string;            // Decimal
  ltv_ratio: string;              // Calculated Decimal
  created_at: ISO8601;
  updated_at: ISO8601;
}
```

**Error Responses:**
```json
{"detail": "Lender not found", "error_code": "APPLICATION_001"} // 404
{"detail": "loan_amount: must be positive Decimal", "error_code": "APPLICATION_002"} // 422
{"detail": "LTV exceeds CMHC insurable limit", "error_code": "APPLICATION_003"} // 409
```

**Request: `POST /api/v1/applications/{app_id}/documents`**
- Content-Type: `multipart/form-data`
- Fields: `file` (binary PDF), `document_type` (enum: `paystub`, `t4`, `bank_statement`, `id_verification`, `property_appraisal`)

**Response: `202 Accepted`**
```typescript
interface DocumentUploadResponse {
  document_id: string;
  status: "queued" | "processing" | "extracted" | "failed";
  presigned_url?: string;         // For viewing (expires in 15min)
}
```

**Error Responses:**
```json
{"detail": "Application not found", "error_code": "APPLICATION_001"} // 404
{"detail": "File exceeds 10MB limit", "error_code": "APPLICATION_004"} // 413
{"detail": "Virus scan failed", "error_code": "APPLICATION_005"} // 422
```

### 1.2 Application Status

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/applications/{app_id}/status` | Authenticated | Get pipeline progress |
| `GET` | `/api/v1/applications/{app_id}/pipeline-events` | Authenticated | SSE stream for real-time updates |

**Response: `GET /api/v1/applications/{app_id}/status`**
```typescript
interface ApplicationStatusResponse {
  application_id: string;
  current_stage: "document_extraction" | "policy_check" | "ratio_calculation" | "decision";
  stage_status: "pending" | "in_progress" | "completed" | "failed";
  stage_progress_percent: number; // 0-100
  estimated_completion: ISO8601 | null;
  pipeline_history: Array<{
    stage: string;
    status: string;
    timestamp: ISO8601;
    metadata: Record<string, any>;
  }>;
}
```

### 1.3 Decision Review

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/applications/{app_id}/decision` | Authenticated | Fetch full decision details |
| `GET` | `/api/v1/applications/{app_id}/audit-trail` | Authenticated | Get immutable audit trail |

**Response: `GET /api/v1/applications/{app_id}/decision`**
```typescript
interface DecisionResponse {
  application_id: string;
  decision_status: "approved" | "rejected" | "referred_to_exception";
  decision_timestamp: ISO8601;
  gds_ratio: string;              // Decimal, e.g., "0.352"
  tds_ratio: string;              // Decimal
  qualifying_rate: string;        // Decimal, per OSFI B-20
  stress_test_applied: boolean;
  cmhc_insurance_required: boolean;
  cmhc_premium_amount: string | null; // Decimal
  flags: Array<{
    code: string;
    severity: "low" | "medium" | "high" | "critical";
    message: string;
    category: "income" | "credit" | "property" | "policy";
  }>;
  ratio_breakdown: {
    gross_monthly_income: string;
    mortgage_payment: string;
    property_tax: string;
    heating_cost: string;
    other_debt_payments: string;
  };
}
```

**Response: `GET /api/v1/applications/{app_id}/audit-trail`**
```typescript
interface AuditTrailResponse {
  application_id: string;
  entries: Array<{
    audit_id: string;
    action: "created" | "document_uploaded" | "extraction_complete" | "ratio_calculated" | "decision_made" | "flag_raised";
    actor_id: string;             // Hashed user ID
    actor_role: "borrower" | "underwriter" | "system";
    timestamp: ISO8601;           // Immutable per FINTRAC
    ip_address?: string;          // For FINTRAC 5-year retention
    user_agent?: string;
    details: Record<string, any>; // JSONB, never mutated
  }>;
}
```

### 1.4 Exception Queue

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/exception-queue` | Underwriter Only | List flagged applications |
| `POST` | `/api/v1/applications/{app_id}/exception-review` | Underwriter Only | Submit human review decision |

**Query Parameters: `GET /api/v1/exception-queue`**
```
?status=flagged&severity=high&sort_by=created_at&order=desc&page=1&limit=20
```

**Response: `200 OK`**
```typescript
interface ExceptionQueueResponse {
  total_count: number;
  page: number;
  limit: number;
  items: Array<{
    application_id: string;
    borrower_sin_hash: string;    // For FINTRAC lookup
    flag_count: number;
    critical_flags: string[];     // Flag codes
    days_in_queue: number;
    assigned_underwriter_id?: string;
    created_at: ISO8601;
  }>;
}
```

---

## 2. Models & Database

### 2.1 Backend SQLAlchemy Models (`modules/applications/models.py`)

```python
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, JSON, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from common.database import Base
import uuid

class Application(Base):
    __tablename__ = "applications"
    
    application_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lender_id = Column(UUID(as_uuid=True), ForeignKey("lenders.lender_id"), nullable=False, index=True)
    status = Column(SQLEnum("draft", "submitted", "extracting", "underwriting", "decision_ready", "approved", "rejected", "exception", name="app_status"), nullable=False, index=True)
    
    # Financial values (Decimal precision for CAD)
    property_value = Column(Numeric(precision=12, scale=2), nullable=False)
    loan_amount = Column(Numeric(precision=12, scale=2), nullable=False)
    ltv_ratio = Column(Numeric(precision=5, scale=4), nullable=False, index=True)
    
    # PIPEDA compliance: SIN stored as hash only
    borrower_sin_hash = Column(String(64), nullable=False, index=True)  # SHA256
    
    # CMHC insurance
    cmhc_insurance_required = Column(Boolean, default=False)
    cmhc_premium_amount = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # OSFI B-20 ratios (stored for audit)
    gds_ratio = Column(Numeric(precision=5, scale=4), nullable=True)
    tds_ratio = Column(Numeric(precision=5, scale=4), nullable=True)
    qualifying_rate = Column(Numeric(precision=5, scale=4), nullable=True)
    
    # Audit fields (FINTRAC immutable)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_by = Column(String(255), nullable=False)  # Hashed user ID
    updated_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="application", uselist=False)
    audit_trail = relationship("AuditLog", back_populates="application", cascade="all, delete-orphan")
    flags = relationship("ExceptionFlag", back_populates="application", cascade="all, delete-orphan")

    __table_args__ = (
        # Composite index for exception queue queries
        Index("ix_applications_status_ltv_created", "status", "ltv_ratio", "created_at"),
        # FINTRAC retention query index
        Index("ix_applications_sin_hash_created", "borrower_sin_hash", "created_at"),
    )


class Document(Base):
    __tablename__ = "documents"
    
    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.application_id"), nullable=False, index=True)
    document_type = Column(SQLEnum("paystub", "t4", "bank_statement", "id_verification", "property_appraisal", name="doc_type"), nullable=False)
    
    # Secure object storage reference (never expose in API)
    s3_key = Column(String(500), nullable=False, unique=True)
    file_name = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    
    # Virus scan status
    scan_status = Column(SQLEnum("pending", "clean", "infected", name="scan_status"), default="pending")
    
    # FINTRAC: Transaction > $10K flag
    transaction_amount_threshold_exceeded = Column(Boolean, default=False)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False)
    created_by = Column(String(255), nullable=False)
    
    application = relationship("Application", back_populates="documents")


class Decision(Base):
    __tablename__ = "decisions"
    
    decision_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.application_id"), nullable=False, unique=True)
    
    decision_status = Column(SQLEnum("approved", "rejected", "referred_to_exception", name="decision_status"), nullable=False, index=True)
    decision_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # OSFI B-20 audit trail (immutable)
    gds_ratio = Column(Numeric(precision=5, scale=4), nullable=False)
    tds_ratio = Column(Numeric(precision=5, scale=4), nullable=False)
    qualifying_rate = Column(Numeric(precision=5, scale=4), nullable=False)  # max(contract_rate + 2%, 5.25%)
    stress_test_applied = Column(Boolean, default=True)
    
    # Ratio breakdown for audit (JSONB per FINTRAC immutable requirement)
    ratio_breakdown = Column(JSONB, nullable=False)  # {gross_monthly_income, mortgage_payment, ...}
    
    application = relationship("Application", back_populates="decisions")


class ExceptionFlag(Base):
    __tablename__ = "exception_flags"
    
    flag_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.application_id"), nullable=False, index=True)
    
    flag_code = Column(String(50), nullable=False, index=True)
    severity = Column(SQLEnum("low", "medium", "high", "critical", name="severity"), nullable=False, index=True)
    message = Column(String(500), nullable=False)
    category = Column(SQLEnum("income", "credit", "property", "policy", name="flag_category"), nullable=False, index=True)
    
    # Underwriter assignment
    assigned_underwriter_id = Column(String(255), nullable=True, index=True)
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    application = relationship("Application", back_populates="flags")
    
    __table_args__ = (
        # Exception queue performance index
        Index("ix_exception_flags_severity_created", "severity", "created_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.application_id"), nullable=False, index=True)
    
    action = Column(String(100), nullable=False, index=True)
    actor_id = Column(String(255), nullable=False, index=True)  # Hashed
    actor_role = Column(String(50), nullable=False)
    
    # FINTRAC 5-year retention requirements
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 support
    user_agent = Column(String(500), nullable=True)
    
    # Immutable details (JSONB)
    details = Column(JSONB, nullable=False)
    
    application = relationship("Application", back_populates="audit_trail")
    
    __table_args__ = (
        # FINTRAC query optimization
        Index("ix_audit_logs_actor_timestamp", "actor_id", "timestamp"),
        Index("ix_audit_logs_application_action", "application_id", "action"),
    )
```

### 2.2 Frontend TypeScript Models (`frontend/src/types/`)

```typescript
// PIPEDA compliance: No SIN/DOB in frontend state
export interface ApplicationDTO {
  application_id: string;
  status: ApplicationStatus;
  lender_id: string;
  property_value: string;  // Decimal string
  loan_amount: string;
  ltv_ratio: string;
  created_at: string;
}

export interface DocumentUploadDTO {
  document_id: string;
  status: "queued" | "processing" | "extracted" | "failed";
  presigned_url?: string;  // Short-lived
}

export interface DecisionDTO {
  application_id: string;
  decision_status: "approved" | "rejected" | "referred_to_exception";
  gds_ratio: string;  // 0.0-1.0
  tds_ratio: string;
  qualifying_rate: string;
  flags: FlagDTO[];
  ratio_breakdown: RatioBreakdownDTO;
}

// Audit trail for UI display
export interface AuditTrailDTO {
  entries: Array<{
    audit_id: string;
    action: string;
    actor_role: string;
    timestamp: string;
    details: Record<string, unknown>;
  }>;
}
```

---

## 3. Business Logic

### 3.1 Document Processing Pipeline State Machine

```python
# modules/applications/services.py
class ApplicationStateMachine:
    """
    FINTRAC compliant immutable state transitions.
    All transitions log to audit_logs table.
    """
    
    ALLOWED_TRANSITIONS = {
        "draft": ["submitted"],
        "submitted": ["extracting"],
        "extracting": ["underwriting", "exception"],
        "underwriting": ["decision_ready", "exception"],
        "decision_ready": ["approved", "rejected", "exception"],
        "exception": ["approved", "rejected"],  # Human review exit
    }
    
    async def transition(self, application_id: UUID, target_status: str, actor_id: str):
        # OSFI B-20: Log all state changes for auditability
        # PIPEDA: actor_id is hashed before logging
        # FINTRAC: IP address and user agent captured from request context
        pass
```

### 3.2 OSFI B-20 Ratio Calculation (Backend)

```python
async def calculate_gds_tds(
    gross_monthly_income: Decimal,
    mortgage_payment: Decimal,
    property_tax: Decimal,
    heating_cost: Decimal,
    other_debt_payments: Decimal,
    contract_rate: Decimal,
) -> Tuple[Decimal, Decimal, Decimal]:
    """
    MANDATORY: Stress test per OSFI B-20
    qualifying_rate = max(contract_rate + 2%, 5.25%)
    GDS = (PITH) / Gross Monthly Income ≤ 39%
    TDS = (PITH + Other Debt) / Gross Monthly Income ≤ 44%
    
    All inputs/outputs are Decimal for precision.
    Logs calculation breakdown for audit.
    """
    qualifying_rate = max(contract_rate + Decimal("0.02"), Decimal("0.0525"))
    
    # PITH calculation using qualifying rate
    pith = mortgage_payment + property_tax + heating_cost
    
    gds = pith / gross_monthly_income
    tds = (pith + other_debt_payments) / gross_monthly_income
    
    # Enforce hard limits
    if gds > Decimal("0.39") or tds > Decimal("0.44"):
        raise UnderwritingRuleViolation("OSFI B-20 thresholds exceeded")
    
    # FINTRAC: Log immutable audit record
    await audit_log_ratio_calculation(
        gds=gds, tds=tds, qualifying_rate=qualifying_rate,
        breakdown={...}  # All components
    )
    
    return gds, tds, qualifying_rate
```

### 3.3 Exception Queue Filtering Logic

```python
# modules/applications/services.py
async def get_exception_queue(
    severity: Optional[List[str]] = None,
    assigned_underwriter: Optional[str] = None,
    sort_by: str = "created_at",
    order: str = "desc",
) -> List[ExceptionFlag]:
    """
    Returns flagged applications for human review.
    FINTRAC: Includes borrower_sin_hash for lookup.
    PIPEDA: No unencrypted PII returned.
    """
    query = select(ExceptionFlag).join(Application).where(
        Application.status == "exception"
    )
    
    if severity:
        query = query.where(ExceptionFlag.severity.in_(severity))
    
    # Underwriter assignment for workload distribution
    if assigned_underwriter:
        query = query.where(ExceptionFlag.assigned_underwriter_id == assigned_underwriter)
    
    query = query.order_by(getattr(ExceptionFlag, sort_by).desc() if order == "desc" else asc)
    
    return await db.execute(query)
```

---

## 4. Migrations

**New Alembic Revision:** `create_applications_module`

```python
# alembic/versions/xxxx_create_applications_module.py

def upgrade():
    # Applications table
    op.create_table(
        "applications",
        sa.Column("application_id", UUID(), nullable=False),
        sa.Column("lender_id", UUID(), nullable=False),
        sa.Column("status", sa.Enum("draft", "submitted", "extracting", "underwriting", "decision_ready", "approved", "rejected", "exception", name="app_status"), nullable=False),
        sa.Column("property_value", Numeric(precision=12, scale=2), nullable=False),
        sa.Column("loan_amount", Numeric(precision=12, scale=2), nullable=False),
        sa.Column("ltv_ratio", Numeric(precision=5, scale=4), nullable=False),
        sa.Column("borrower_sin_hash", String(64), nullable=False),
        sa.Column("cmhc_insurance_required", Boolean, default=False),
        sa.Column("cmhc_premium_amount", Numeric(precision=10, scale=2), nullable=True),
        sa.Column("gds_ratio", Numeric(precision=5, scale=4), nullable=True),
        sa.Column("tds_ratio", Numeric(precision=5, scale=4), nullable=True),
        sa.Column("qualifying_rate", Numeric(precision=5, scale=4), nullable=True),
        sa.Column("created_at", DateTime(timezone=True), nullable=False),
        sa.Column("created_by", String(255), nullable=False),
        sa.Column("updated_at", DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("application_id"),
        sa.ForeignKeyConstraint(["lender_id"], ["lenders.lender_id"]),
        sa.Index("ix_applications_status_ltv_created", "status", "ltv_ratio", "created_at"),
        sa.Index("ix_applications_sin_hash_created", "borrower_sin_hash", "created_at"),
    )
    
    # Documents table
    op.create_table(
        "documents",
        sa.Column("document_id", UUID(), nullable=False),
        sa.Column("application_id", UUID(), nullable=False),
        sa.Column("document_type", sa.Enum(...), nullable=False),
        sa.Column("s3_key", String(500), nullable=False, unique=True),
        sa.Column("file_name", String(255), nullable=False),
        sa.Column("file_size_bytes", Integer, nullable=False),
        sa.Column("mime_type", String(100), nullable=False),
        sa.Column("scan_status", sa.Enum("pending", "clean", "infected", name="scan_status"), default="pending"),
        sa.Column("transaction_amount_threshold_exceeded", Boolean, default=False),
        sa.Column("created_at", DateTime(timezone=True), nullable=False),
        sa.Column("created_by", String(255), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.application_id"]),
        sa.PrimaryKeyConstraint("document_id"),
        sa.Index("ix_documents_application_type", "application_id", "document_type"),
    )
    
    # Decisions table
    op.create_table(
        "decisions",
        sa.Column("decision_id", UUID(), nullable=False),
        sa.Column("application_id", UUID(), nullable=False, unique=True),
        sa.Column("decision_status", sa.Enum(...), nullable=False),
        sa.Column("decision_timestamp", DateTime(timezone=True), nullable=False),
        sa.Column("gds_ratio", Numeric(precision=5, scale=4), nullable=False),
        sa.Column("tds_ratio", Numeric(precision=5, scale=4), nullable=False),
        sa.Column("qualifying_rate", Numeric(precision=5, scale=4), nullable=False),
        sa.Column("stress_test_applied", Boolean, default=True),
        sa.Column("ratio_breakdown", JSONB, nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.application_id"]),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.Index("ix_decisions_timestamp", "decision_timestamp"),
    )
    
    # Exception flags table
    op.create_table(
        "exception_flags",
        sa.Column("flag_id", UUID(), nullable=False),
        sa.Column("application_id", UUID(), nullable=False),
        sa.Column("flag_code", String(50), nullable=False),
        sa.Column("severity", sa.Enum(...), nullable=False),
        sa.Column("message", String(500), nullable=False),
        sa.Column("category", sa.Enum(...), nullable=False),
        sa.Column("assigned_underwriter_id", String(255), nullable=True),
        sa.Column("created_at", DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.application_id"]),
        sa.PrimaryKeyConstraint("flag_id"),
        sa.Index("ix_exception_flags_severity_created", "severity", "created_at"),
        sa.Index("ix_exception_flags_assigned_underwriter", "assigned_underwriter_id", "created_at"),
    )
    
    # Audit logs table (FINTRAC immutable)
    op.create_table(
        "audit_logs",
        sa.Column("audit_id", UUID(), nullable=False),
        sa.Column("application_id", UUID(), nullable=False),
        sa.Column("action", String(100), nullable=False),
        sa.Column("actor_id", String(255), nullable=False),
        sa.Column("actor_role", String(50), nullable=False),
        sa.Column("timestamp", DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", String(45), nullable=True),
        sa.Column("user_agent", String(500), nullable=True),
        sa.Column("details", JSONB, nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.application_id"]),
        sa.PrimaryKeyConstraint("audit_id"),
        sa.Index("ix_audit_logs_actor_timestamp", "actor_id", "timestamp"),
        sa.Index("ix_audit_logs_application_action", "application_id", "action"),
    )

def downgrade():
    # NEVER delete data in production per FINTRAC
    # Create archive tables instead
    pass
```

---

## 5. Security & Compliance

### 5.1 PIPEDA (Frontend & Backend)

**Frontend:**
- **Encryption at Rest:** Browser `crypto.subtle.encrypt()` for temporary SIN/DOB entry before hashing
- **Data Minimization:** Components never store SIN/DOB in state or localStorage
- **Secure Communication:** All API calls via HTTPS with TLS 1.3
- **Content Security Policy:** `default-src 'self'; script-src 'self' 'nonce-<random>'; object-src 'none'`
- **No PII in Logs:** Frontend structlog filters out SIN, DOB, income fields before sending to logging endpoint

**Backend:**
- **AES-256 Encryption:** SIN/DOB encrypted in `borrowers` table (separate from hash)
- **Hash Only for Lookups:** `borrower_sin_hash` column used for all queries; raw SIN never logged
- **API Response Filtering:** Pydantic schemas exclude encrypted fields
- **Error Messages:** Generic "validation failed" instead of field-specific PII leaks

### 5.2 FINTRAC (Backend)

**Mandatory Implementation:**
- **Immutable Audit Trail:** `audit_logs` table has no UPDATE/DELETE operations
- **Transaction Threshold Flag:** `documents.transaction_amount_threshold_exceeded` auto-set if PDF parsing detects > CAD $10,000
- **5-Year Retention:** All `created_at` timestamps preserved; soft-delete only via `archived_at` flag
- **Actor Identification:** `actor_id` is SHA256 hash of JWT `sub` claim; `actor_role` from JWT `role` claim
- **IP & User Agent:** Captured from FastAPI `Request` object for every mutation endpoint

**Reporting Trigger:**
```python
# In document upload service
if parsed_transaction_amount > 10000:
    await flag_fintrac_reporting_required(application_id, document_id)
    document.transaction_amount_threshold_exceeded = True
```

### 5.3 OSFI B-20 (Backend)

**Stress Test Enforcement:**
```python
# In underwriting service
qualifying_rate = max(contract_rate + Decimal("0.02"), Decimal("0.0525"))
if gds_ratio > Decimal("0.39") or tds_ratio > Decimal("0.44"):
    raise BusinessRuleViolation(
        detail="OSFI B-20 thresholds exceeded",
        error_code="UNDERWRITING_003",
        audit_payload={"gds": str(gds), "tds": str(tds), "qualifying_rate": str(qualifying_rate)}
    )
```

**Audit Logging:**
- Every ratio calculation logged to `audit_logs.details` with full breakdown
- `qualifying_rate` stored in `decisions` table for regulator review

### 5.4 CMHC Insurance (Backend)

**Premium Calculation:**
```python
ltv = loan_amount / property_value
if ltv > Decimal("0.80"):
    insurance_required = True
    if Decimal("0.8001") <= ltv <= Decimal("0.85"):
        premium_rate = Decimal("0.0280")
    elif Decimal("0.8501") <= ltv <= Decimal("0.90"):
        premium_rate = Decimal("0.0310")
    elif Decimal("0.9001") <= ltv <= Decimal("0.95"):
        premium_rate = Decimal("0.0400")
    else:
        raise UninsurableLTV("LTV exceeds 95%")
    
    premium_amount = loan_amount * premium_rate
```

### 5.5 Authentication & Authorization

**JWT Claims Required:**
```json
{
  "sub": "user_sha256_hash",
  "role": "borrower|underwriter|admin",
  "lender_id": "uuid-or-null",
  "exp": 1704067200
}
```

**Endpoint Permissions:**
- `/api/v1/applications/*`: Requires `role: borrower` (own apps) or `role: underwriter` (all apps)
- `/api/v1/exception-queue`: Requires `role: underwriter`
- `/api/v1/applications/{app_id}/decision`: Borrower can view only their own decisions

---

## 6. Error Codes & HTTP Responses

### 6.1 Application Module Exceptions (`modules/applications/exceptions.py`)

```python
from common.exceptions import AppException

class ApplicationNotFoundError(AppException):
    """Raised when application ID does not exist"""
    status_code = 404
    error_code = "APPLICATION_001"
    message_template = "Application {application_id} not found"

class ApplicationValidationError(AppException):
    """Raised when Pydantic validation fails"""
    status_code = 422
    error_code = "APPLICATION_002"
    message_template = "{field}: {reason}"

class BusinessRuleViolation(AppException):
    """Raised when OSFI B-20, CMHC, or FINTRAC rules are violated"""
    status_code = 409
    error_code = "APPLICATION_003"
    message_template = "Business rule violated: {rule_name}"
    
    def __init__(self, detail: str, error_code: str, audit_payload: dict):
        super().__init__(detail, error_code)
        self.audit_payload = audit_payload  # Auto-logged to audit_logs

class DocumentUploadError(AppException):
    """Raised when file upload fails security/validation"""
    status_code = 413
    error_code = "APPLICATION_004"
    message_template = "Document upload failed: {reason}"

class VirusDetectedError(AppException):
    """Raised when ClamAV scan finds malware"""
    status_code = 422
    error_code = "APPLICATION_005"
    message_template = "Virus detected in file: {file_name}"
    # FINTRAC: Logs file hash and timestamp for reporting
```

### 6.2 Frontend Error Handling

**Axios Interceptor Pattern:**
```typescript
// frontend/src/api/interceptors.ts
axios.interceptors.response.use(
  response => response,
  error => {
    const errorCode = error.response?.data?.error_code;
    
    // PIPEDA: Sanitize error messages before display
    if (errorCode === "APPLICATION_002") {
      // Show generic message, log detailed to secure endpoint
      logger.error("Validation error", { error_code: errorCode, fields: sanitize(error.response.data.detail) });
      toast.error("Please check your input and try again.");
    }
    
    if (errorCode === "APPLICATION_003") {
      // OSFI B-20 violation
      toast.error("Application does not meet underwriting guidelines.", { duration: 5000 });
    }
    
    return Promise.reject(error);
  }
);
```

**Structured Error Response Format:**
All backend errors return:
```json
{
  "detail": "Human-readable message (no PII)",
  "error_code": "APPLICATION_XXX",
  "correlation_id": "uuid-for-tracing",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

---

## 7. React UI Architecture (Supplementary)

**Tech Stack:**
- **Framework:** React 18.2+ with TypeScript 5.0+
- **State Management:** Zustand (lightweight, no PII in store)
- **Styling:** Tailwind CSS 3.4+ (WCAG 2.1 AA compliant color palette)
- **Charts:** Recharts (for ratio visualizations)
- **File Upload:** react-dropzone with PDF.js preview
- **SSE:** Native EventSource API for real-time pipeline updates
- **Testing:** Vitest + React Testing Library (unit), Playwright (integration)

**Component Structure:**
```
frontend/src/
├── pages/
│   ├── ApplicationSubmission.tsx  # Document uploader, lender select
│   ├── ApplicationStatus.tsx      # Progress indicators
│   ├── DecisionReview.tsx         # Ratio charts, flags
│   └── ExceptionQueue.tsx         # Data table with filters
├── components/
│   ├── DocumentUploader.tsx       # Drag-and-drop, virus scan status
│   ├── PipelineProgress.tsx       # Stepper with SSE updates
│   ├── RatioVisualization.tsx     # GDS/TDS gauge charts
│   ├── AuditTrailViewer.tsx       # Collapsible timeline
│   └── ExceptionQueueTable.tsx    # Sortable, filterable data grid
├── hooks/
│   useApplicationStatus.ts        # SSE subscription
│   useAuditTrail.ts               # Fetch with React Query
│   useExceptionQueue.ts           # Filter/sort state
└── utils/
    piiSanitizer.ts                # Strip PII from errors
    decimalFormatter.ts            # Format Decimal strings for UI
```

**Accessibility (WCAG 2.1 AA):**
- All form inputs have `aria-label` and `aria-describedby`
- Color contrast ratio ≥ 4.5:1 (Tailwind `gray-900` on `white`)
- Keyboard navigation for all interactive elements
- `react-dropzone` provides `role="button"` and `tabIndex=0`

**Performance:**
- Code splitting via Vite `rollupOptions`
- Lazy load `Recharts` and PDF.js on demand
- React.memo for `RatioVisualization` component (heavy re-renders)
- API pagination for exception queue (limit=20)

---

## 8. Regulatory Checklist

| Requirement | Implementation | Verification |
|-------------|----------------|--------------|
| **OSFI B-20** | Stress test in `calculate_gds_tds()`, hard limits enforced | Unit tests with 5.25% floor, contract_rate + 2% scenarios |
| **FINTRAC** | `audit_logs` table immutable, 5-year retention, IP capture | Integration tests verify no UPDATE/DELETE; archive job tested |
| **CMHC** | Premium tier lookup in `Application.create()`, LTV > 80% flag | Unit tests for each tier boundary (80.01%, 85.01%, 90.01%) |
| **PIPEDA** | SIN hashed, encrypted at rest, never in logs/API responses | Code scan for `sin` string literals; log redaction tests |
| **WCAG 2.1** | Aria labels, keyboard nav, color contrast | Playwright axe-core tests on each page |

---