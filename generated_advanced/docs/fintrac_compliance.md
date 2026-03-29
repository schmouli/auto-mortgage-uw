# FINTRAC Compliance
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# FINTRAC Compliance Module Design

**File:** `docs/design/fintrac-compliance.md`  
**Module:** `modules/fintrac/`  
**Compliance Framework:** FINTRAC PCMLTFA, PIPEDA, OSFI B-20 (indirect)  
**Last Updated:** 2024

---

## 1. Endpoints

### `POST /api/v1/fintrac/applications/{application_id}/verify-identity`
Submit identity verification record for a client associated with a mortgage application.

**Authentication:** JWT required (roles: `underwriter`, `compliance_officer`, `admin`)  
**Authorization:** User must be assigned to the application or have `compliance_officer` role

**Request Schema:**
```python
class FintracVerificationRequest(BaseModel):
    client_id: UUID
    verification_method: Literal["in_person", "credit_file", "dual_process"]
    id_type: str  # e.g., "driver_license", "passport"
    id_number: str  # Plaintext; encrypted at rest
    id_expiry_date: date
    id_issuing_province: str  # 2-letter province code
    is_pep: bool = False
    is_hio: bool = False
```

**Response Schema (201 Created):**
```python
class FintracVerificationResponse(BaseModel):
    verification_id: UUID
    application_id: UUID
    client_id: UUID
    verification_method: str
    risk_level: Literal["low", "medium", "high"]
    verified_at: datetime
    requires_enhanced_due_diligence: bool
    detail: str = "Identity verification recorded"
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `FINTRAC_001` | Application or client not found |
| 409 | `FINTRAC_003` | Verification already exists for this client (idempotent if same data) |
| 422 | `FINTRAC_002` | Invalid province code, expired ID, or missing required fields |
| 403 | `AUTH_002` | User not authorized for this application |

**Edge Cases:**
- Duplicate submission within 5 minutes: return existing record with `200 OK`
- ID expiry < 30 days: triggers `warning` in response but succeeds
- PEP/HIO true: auto-sets `risk_level=high` and flags for enhanced diligence

---

### `GET /api/v1/fintrac/applications/{application_id}/verification`
Retrieve identity verification status for all clients on an application.

**Authentication:** JWT required (roles: `underwriter`, `compliance_officer`, `admin`)  
**Authorization:** User must be assigned to the application or have `compliance_officer` role

**Response Schema (200 OK):**
```python
class FintracVerificationStatusResponse(BaseModel):
    application_id: UUID
    verifications: List[FintracVerificationSummary]
    
class FintracVerificationSummary(BaseModel):
    verification_id: UUID
    client_id: UUID
    verification_method: str
    risk_level: str
    verified_at: datetime
    is_pep: bool
    is_hio: bool
    status: Literal["pending", "verified", "flagged"]
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `FINTRAC_001` | Application not found |
| 403 | `AUTH_002` | User not authorized |

**Security Note:** `id_number` and `id_expiry_date` are **excluded** from response (PIPEDA compliance).

---

### `POST /api/v1/fintrac/applications/{application_id}/report-transaction`
File a FINTRAC report for large cash or suspicious transactions.

**Authentication:** JWT required (roles: `compliance_officer`, `admin`)  
**Authorization:** Must have `compliance_officer` role

**Request Schema:**
```python
class FintracReportRequest(BaseModel):
    report_type: Literal["large_cash_transaction", "suspicious_transaction", "terrorist_property"]
    amount: Decimal  # Must be > 10000.00 CAD for LCT
    currency: str = "CAD"
    transaction_date: datetime
    transaction_details: str  # Free text describing the transaction
    client_id: UUID  # Required for suspicious/terrorist reports
```

**Response Schema (202 Accepted):**
```python
class FintracReportResponse(BaseModel):
    report_id: UUID
    application_id: UUID
    report_type: str
    amount: Decimal
    status: Literal["draft", "submitted", "acknowledged"]
    fintrac_reference_number: Optional[str] = None
    detail: str = "Report queued for FINTRAC submission"
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 422 | `FINTRAC_002` | Amount ≤ $10,000 CAD for LCT, or missing required fields |
| 409 | `FINTRAC_003` | Structuring pattern detected (auto-flagged) |
| 404 | `FINTRAC_001` | Application or client not found |
| 403 | `AUTH_003` | Insufficient privileges (requires compliance_officer) |

**Business Rule:** System auto-rejects LCT reports below threshold; suspicious reports have no minimum.

---

### `GET /api/v1/fintrac/applications/{application_id}/reports`
List all FINTRAC reports filed for an application.

**Authentication:** JWT required (roles: `underwriter`, `compliance_officer`, `admin`)  
**Authorization:** User must be assigned to the application or have `compliance_officer` role

**Query Parameters:**
- `report_type`: Optional filter
- `status`: Optional filter
- `date_from`, `date_to`: Optional date range (ISO 8601)

**Response Schema (200 OK):**
```python
class FintracReportsListResponse(BaseModel):
    application_id: UUID
    reports: List[FintracReportSummary]
    
class FintracReportSummary(BaseModel):
    report_id: UUID
    report_type: str
    amount: Decimal
    currency: str
    report_date: datetime
    status: str
    fintrac_reference_number: Optional[str]
    created_by: UUID
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `FINTRAC_001` | Application not found |
| 403 | `AUTH_002` | User not authorized |

---

### `GET /api/v1/fintrac/risk-assessment/{client_id}`
Retrieve aggregated risk assessment for a client across all applications.

**Authentication:** JWT required (roles: `underwriter`, `compliance_officer`, `admin`)  
**Authorization:** User must have `compliance_officer` role or be assigned to an active application with this client

**Response Schema (200 OK):**
```python
class ClientRiskAssessmentResponse(BaseModel):
    client_id: UUID
    overall_risk_level: Literal["low", "medium", "high"]
    risk_score: int  # 0-100
    factors: List[RiskFactor]
    open_alerts: int
    fintrac_reports_count: int
    
class RiskFactor(BaseModel):
    category: str  # "pep", "hio", "verification", "structuring"
    severity: int  # 0-100
    description: str
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| 404 | `FINTRAC_004` | Client not found or no access |
| 403 | `AUTH_002` | User not authorized |

---

## 2. Models & Database

### `modules/fintrac/models.py`

#### Table: `fintrac_verifications`
```python
class FintracVerification(Base):
    __tablename__ = "fintrac_verifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Verification details
    verification_method = Column(Enum("in_person", "credit_file", "dual_process", name="verification_method_enum"), nullable=False)
    id_type = Column(String(50), nullable=False)  # e.g., 'driver_license'
    id_number_encrypted = Column(LargeBinary, nullable=False)  # AES-256 encrypted
    id_expiry_date = Column(Date, nullable=False)
    id_issuing_province = Column(String(2), nullable=False)  # ISO 3166-2
    
    # Verification metadata
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Risk flags
    is_pep = Column(Boolean, default=False, nullable=False, index=True)
    is_hio = Column(Boolean, default=False, nullable=False, index=True)
    risk_level = Column(Enum("low", "medium", "high", name="risk_level_enum"), nullable=False, index=True)
    
    # FINTRAC audit trail (immutable)
    record_created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    record_created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Soft-delete only (5-year retention)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Relationships
    application = relationship("Application", back_populates="fintrac_verifications")
    client = relationship("Client", back_populates="fintrac_verifications")
    verifier = relationship("User", foreign_keys=[verified_by])
    
    # Indexes
    __table_args__ = (
        # Composite for structuring detection queries
        Index("idx_verifications_client_created", "client_id", "record_created_at"),
        # Composite for risk assessment dashboard
        Index("idx_verifications_pep_hio_risk", "is_pep", "is_hio", "risk_level"),
        # Unique per client per application (one verification allowed)
        UniqueConstraint("application_id", "client_id", name="uq_verification_per_client"),
        # Check constraint for valid province codes
        CheckConstraint(
            "id_issuing_province IN ('AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT')",
            name="chk_valid_province"
        ),
    )
```

#### Table: `fintrac_reports`
```python
class FintracReport(Base):
    __tablename__ = "fintrac_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=True, index=True)  # Optional for LCT
    
    # Report details
    report_type = Column(
        Enum("large_cash_transaction", "suspicious_transaction", "terrorist_property", name="report_type_enum"),
        nullable=False,
        index=True
    )
    amount = Column(DECIMAL(15, 2), nullable=False)  # FINTRAC requirement: no precision loss
    currency = Column(String(3), default="CAD", nullable=False)
    
    # Timeline
    transaction_date = Column(TIMESTAMP(timezone=True), nullable=False)
    report_date = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    submitted_to_fintrac_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # FINTRAC acknowledgement
    fintrac_reference_number = Column(String(100), nullable=True, unique=True)
    
    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    record_created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    record_updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Soft-delete (retention)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Relationships
    application = relationship("Application", back_populates="fintrac_reports")
    client = relationship("Client", back_populates="fintrac_reports")
    
    # Indexes
    __table_args__ = (
        # For threshold monitoring queries
        Index("idx_reports_amount_currency", "amount", "currency"),
        # For date-range queries
        Index("idx_reports_transaction_date", "transaction_date"),
        # For submission tracking
        Index("idx_reports_submitted_null", "submitted_to_fintrac_at"),
        # Check constraint: amount must be positive
        CheckConstraint("amount > 0", name="chk_positive_amount"),
    )
```

#### Table: `fintrac_structuring_alerts`
```python
class FintracStructuringAlert(Base):
    __tablename__ = "fintrac_structuring_alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Structuring pattern details
    transaction_count = Column(Integer, nullable=False)
    total_amount = Column(DECIMAL(15, 2), nullable=False)
    time_window_start = Column(TIMESTAMP(timezone=True), nullable=False)
    time_window_end = Column(TIMESTAMP(timezone=True), nullable=False)
    
    # Alert status
    alert_status = Column(Enum("open", "investigated", "report_filed", "closed", name="alert_status_enum"), nullable=False, default="open")
    
    # Audit
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    client = relationship("Client", back_populates="structuring_alerts")
    
    # Indexes
    __table_args__ = (
        Index("idx_structuring_client_window", "client_id", "time_window_start", "time_window_end"),
        Index("idx_structuring_status", "alert_status"),
    )
```

**Encryption Requirements (PIPEDA):**
- `id_number_encrypted`: AES-256-GCM encryption via `common/security.encrypt_pii()`
- Encryption key rotation: Every 90 days via `common/security.rotate_encryption_key()`
- Key ID stored in separate `encryption_key_versions` table (common module)

---

## 3. Business Logic

### Identity Verification Workflow
```python
# modules/fintrac/services.py

async def verify_identity(
    application_id: UUID,
    client_id: UUID,
    verification_method: str,
    id_type: str,
    id_number: str,
    id_expiry_date: date,
    id_issuing_province: str,
    is_pep: bool,
    is_hio: bool,
    verified_by: UUID
) -> FintracVerification:
    """
    Algorithm:
    1. Validate application exists and is in "underwriting" state
    2. Validate client exists and is linked to application
    3. Validate province code against Canadian provinces
    4. Check ID expiry date (reject if expired)
    5. Encrypt id_number using encrypt_pii()
    6. Calculate risk_score:
       - base_score = 0
       - method_score: in_person=0, credit_file=10, dual_process=0
       - pep_score: is_pep=True → +50
       - hio_score: is_hio=True → +30
       - province_score: ON/BC/AB=0, others=5
       - expiry_score: expires < 30 days → +10
       - total_score = base + method + pep + hio + province + expiry
    7. Determine risk_level:
       - 0-20: low
       - 21-50: medium
       - 51+: high
    8. Set requires_enhanced_due_diligence = (risk_level == "high" or is_pep or is_hio)
    9. Create verification record with audit fields
    10. Log audit event (exclude id_number): 
        {"event": "identity_verified", "application_id": "...", "client_id": "...", "risk_level": "high"}
    11. If requires_enhanced_due_diligence: trigger notification to compliance team
    """
```

### Risk Scoring Algorithm Details
**Weights and Factors:**
| Factor | Weight | Calculation |
|--------|--------|-------------|
| Verification Method | 0-10 | in_person=0, credit_file=10, dual_process=0 |
| PEP Status | 50 | Boolean: True=50, False=0 |
| HIO Status | 30 | Boolean: True=30, False=0 |
| Province | 0-5 | High-risk provinces (NT, NU, YT)=5, others=0 |
| ID Expiry Proximity | 0-10 | < 30 days=10, < 90 days=5, else=0 |
| **Total Score** | **0-105** | **risk_level = low (0-20), medium (21-50), high (51+)** |

**Enhanced Due Diligence Triggers:**
- Automatic if `risk_level == "high"` OR `is_pep == True` OR `is_hio == True`
- Requires additional documentation and supervisor approval before proceeding to approval

### Transaction Monitoring & Structuring Detection
```python
async def monitor_transaction(transaction: TransactionEvent):
    """
    Algorithm:
    1. If transaction.cash_amount > 10000.00 CAD:
       - Create fintrac_reports(type="large_cash_transaction")
       - Set status="draft"
       - Queue for compliance officer review
    
    2. Else if transaction.cash_amount < 10000.00 CAD:
       - Query fintrac_reports for same client_id within 24h
       - Sum all cash amounts in time window
       - If sum > 10000.00:
         - Create fintrac_structuring_alerts
         - Create fintrac_reports(type="suspicious_transaction", reason="structuring")
         - Notify compliance team via webhook
    
    3. Threshold configuration:
       - Threshold = config.get("fintrac_large_cash_threshold", 10000.00)
       - Time window = config.get("fintrac_structuring_window_hours", 24)
    
    4. Logging: Log detection event with correlation_id, exclude PII
    """
```

### State Machine: Verification Status
```
pending → verified → (if flagged) → enhanced_due_diligence → approved/rejected
     ↳ skipped (if exempt)
```

### State Machine: Report Status
```
draft → submitted → acknowledged → closed
   ↳ rejected (if invalid)
```

### Retention Policy
- **Active Records:** Never hard-deleted; soft-delete flag only
- **5-Year Retention:** Background job `retention_worker` runs monthly
  - Marks records `is_deleted=True` where `record_created_at < now - 5 years`
  - Archives to cold storage (S3 Glacier with encryption)
- **Access:** Soft-deleted records excluded from all queries by default; compliance officers can query with `include_deleted=true` parameter

---

## 4. Migrations

### Alembic Migration: `2024_01_create_fintrac_tables.py`

**New Tables:**
1. `fintrac_verifications`
2. `fintrac_reports`
3. `fintrac_structuring_alerts`

**Columns to Add to Existing Tables:**
- `applications.fintrac_status` (ENUM: "pending", "cleared", "flagged") - for dashboard filtering
- `clients.pep_hio_last_checked` (TIMESTAMP) - cache PEP/HIO list check date
- `clients.pep_hio_status` (JSONB) - store external list metadata

**Indexes:**
```sql
-- fintrac_verifications
CREATE INDEX idx_verifications_app_client ON fintrac_verifications(application_id, client_id);
CREATE INDEX idx_verifications_risk_created ON fintrac_verifications(risk_level, record_created_at);

-- fintrac_reports
CREATE INDEX idx_reports_type_unsubmitted ON fintrac_reports(report_type) WHERE submitted_to_fintrac_at IS NULL;
CREATE INDEX idx_reports_amount_threshold ON fintrac_reports(amount) WHERE amount > 10000.00;

-- fintrac_structuring_alerts
CREATE INDEX idx_structuring_open ON fintrac_structuring_alerts(alert_status) WHERE alert_status = 'open';
```

**Data Migration Needs:**
- Backfill `applications.fintrac_status` based on existing verification records
- Initial seed of `encryption_key_versions` table for PII encryption keys
- **NO modification of existing client PII columns** (handled by common module)

---

## 5. Security & Compliance

### FINTRAC PCMLTFA Requirements

| Requirement | Implementation |
|-------------|----------------|
| **Identity Verification** | All clients verified via `verify-identity` endpoint; method recorded |
| **Large Cash Transactions** | Auto-detected at > $10,000 CAD; report queued within 15 days |
| **Suspicious Transaction Reports** | Structuring detection algorithm; manual flagging via `report-transaction` |
| **Terrorist Property** | Manual report type; requires admin role |
| **Record Retention** | Soft-delete only; 5-year retention enforced by background worker |
| **Immutability** | `record_created_at` and `record_created_by` never updated; separate `updated_at` column |
| **Structuring Detection** | 24-hour rolling window; auto-flag multiple sub-threshold transactions |

### PIPEDA Data Handling

**Encrypted Fields:**
- `id_number_encrypted` (AES-256-GCM)
- SIN/DOB encryption handled by `common/security.py` (referenced, not duplicated)

**Data Minimization:**
- `id_number` collected only for verification; never stored in logs
- `transaction_details` free-text limited to 500 chars; excludes PII
- API responses exclude encrypted fields and SIN/DOB

**Logging:**
```python
# structlog JSON format
{
    "event": "fintrac_report_created",
    "correlation_id": "uuid",
    "application_id": "uuid",
    "report_type": "large_cash_transaction",
    "amount": "15000.00",  # Decimal as string
    # NO: id_number, sin, dob, client_name
}
```

### Authentication & Authorization

| Endpoint | Required Role | Scope |
|----------|---------------|-------|
| `POST /verify-identity` | `underwriter`, `compliance_officer`, `admin` | Application-level access |
| `GET /verification` | `underwriter`, `compliance_officer`, `admin` | Application-level access |
| `POST /report-transaction` | `compliance_officer`, `admin` | System-wide access |
| `GET /reports` | `underwriter`, `compliance_officer`, `admin` | Application-level access |
| `GET /risk-assessment/{client_id}` | `compliance_officer`, `admin` | Client-level access control |

**mTLS:** FINTRAC submission API integration uses mutual TLS (certs in `common/config.py`).

### OSFI B-20间接Compliance
- FINTRAC module **does not calculate GDS/TDS** but **blocks** applications with `risk_level=high` from proceeding to approval until cleared by compliance officer
- Integration point: Underwriting service calls `GET /risk-assessment` before final approval

---

## 6. Error Codes & HTTP Responses

### Custom Exception Hierarchy (in `modules/fintrac/exceptions.py`)

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Example |
|-----------------|-------------|------------|-----------------|-----------------|
| `FintracVerificationNotFoundError` | 404 | `FINTRAC_001` | "Verification not found for application {id}" | GET verification when none exists |
| `FintracValidationError` | 422 | `FINTRAC_002` | "{field}: {reason}" | Invalid province code, expired ID |
| `FintracBusinessRuleError` | 409 | `FINTRAC_003` | "{rule} violated: {detail}" | LCT amount ≤ $10,000, duplicate verification |
| `FintracStructuringDetectedError` | 409 | `FINTRAC_004` | "Structuring pattern detected: {total_amount} in {window}" | Multiple sub-threshold transactions |
| `FintracReportNotFoundError` | 404 | `FINTRAC_005` | "FINTRAC report {id} not found" | GET non-existent report |
| `FintracClientRiskNotFoundError` | 404 | `FINTRAC_006` | "Risk assessment not available for client {id}" | Client has no verifications |

### Error Response Format
```json
{
  "detail": "Large cash transaction threshold violated: amount 5000.00 <= 10000.00",
  "error_code": "FINTRAC_003",
  "correlation_id": "a1b2c3d4-e5f6-7890",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

### Retry Logic
- FINTRAC API submission failures: Exponential backoff (1h, 2h, 4h, 8h, 24h)
- Max retries: 5; then alert compliance team via Slack/Email
- Idempotency: `fintrac_reference_number` ensures duplicate submissions are rejected

---

## 7. Integration & Missing Details (WARNING)

**PEP/HIO List Automation:**
- **WARNING:** External PEP/HIO list integration not specified in requirements
- **Proposed Solution:** Cache list from FINTRAC API in `clients.pep_hio_status` JSONB; refresh daily via background job `pep_hio_sync_worker`
- **Fallback:** Manual flagging via `is_pep`/`is_hio` booleans in verification request

**FINTRAC Submission API:**
- **WARNING:** API specs not provided
- **Design Assumption:** RESTful API with mTLS auth; async webhook for acknowledgements
- **Endpoint:** `POST https://api.fintrac-canafe.gc.ca/v1/reports` (placeholder)
- **Timeout:** 30s; circuit breaker after 3 failures

**Risk Scoring Weights:**
- **WARNING:** Weights are based on FINTRAC guidance but may require tuning
- **Recommendation:** A/B test weights with compliance team; store model version in `risk_score_model_version` column

**Transaction Monitoring Thresholds:**
- **WARNING:** $10,000 CAD threshold is statutory; structuring detection window (24h) is configurable
- **Recommendation:** Add `fintrac_config` table for threshold tuning without code deploy

**Audit Trail Completeness:**
- **WARNING:** FINTRAC requires **every action** on a report to be logged
- **Implementation:** `FintracAuditLog` table with `action`, `user_id`, `timestamp`, `ip_address` for all report state changes

---

## 8. Testing Strategy

### Unit Tests (`tests/unit/test_fintrac.py`)
- Risk scoring algorithm (all factor combinations)
- Encryption/decryption round-trip
- Structuring detection logic (edge cases: exactly 24h, timezone boundaries)
- Validation: province codes, expiry dates, amount thresholds

### Integration Tests (`tests/integration/test_fintrac_integration.py`)
- Full verification flow: POST → GET → risk assessment
- Report submission: Queue → Worker → Mock FINTRAC API
- Structuring detection: Multiple transactions in 24h window
- Soft-delete retention: Verify records exist after delete flag set
- Authorization: Role-based access control matrix

**Test Data:**
- Mock PEP/HIO list API responses
- Mock FINTRAC submission API (200, 400, 500 scenarios)
- Pre-encrypted ID numbers using test encryption key

---

## 9. Observability

### Metrics (`/metrics` Prometheus)
```
fintrac_verifications_total{method="in_person", risk_level="high"} 42
fintrac_reports_pending{report_type="large_cash_transaction"} 3
fintrac_structuring_alerts_open 1
fintrac_api_submissions_failed_total 0
```

### Logging (structlog)
- **INFO:** Verification created, report filed, structuring detected
- **WARNING:** ID expiry < 30 days, PEP/HIO manual override
- **ERROR:** FINTRAC API submission failure, encryption key rotation failure
- **CRITICAL:** Structuring alert not processed (compliance risk)

### Tracing (OpenTelemetry)
- Trace verification flow: API → Service → DB → Encryption
- Trace FINTRAC submission: Worker → HTTP Client → FINTRAC API
- Baggage: `client_id`, `application_id` for cross-service correlation

---

**Compliance Sign-off Required:** This module must be reviewed by internal compliance and legal teams before production deployment. FINTRAC reporting obligations are statutory; misconfiguration may result in penalties.