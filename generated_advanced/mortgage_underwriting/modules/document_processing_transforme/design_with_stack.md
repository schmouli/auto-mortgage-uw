# Design: Document Processing Transformer (DPT) Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Document Processing Transformer (DPT) Service Design Plan

**File:** `docs/design/dpt-service.md`  
**Module:** `modules/dpt/`  
**Version:** 1.0.0  
**Last Updated:** 2024-01-15

---

## 1. Endpoints

### `POST /api/v1/dpt/extract`
Submit a mortgage document for asynchronous extraction.

**Authentication:** JWT required (roles: `borrower`, `broker`, `underwriter`)

**Request Schema:**
```python
class DPTExtractionRequest(BaseModel):
    application_id: UUID  # FK to applications table
    document_type: Literal["t4", "t4a", "noa", "credit_report", "bank_statement", "purchase_agreement"]
    s3_key: str  # S3 object key (e.g., "uploads/{app_id}/document.pdf")
    filename: str  # Original filename for audit logging
    correlation_id: Optional[UUID] = None  # For distributed tracing
```

**Response Schema (201 Created):**
```python
class DPTExtractionResponse(BaseModel):
    job_id: UUID
    status: Literal["pending", "processing", "success", "failed"]
    submitted_at: datetime
    estimated_completion: datetime  # Now + queue depth estimate
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| `400` | `DPT_006` | `document_type` not in allowed enum |
| `401` | `AUTH_001` | Missing or invalid JWT token |
| `403` | `AUTH_002` | User lacks permission for `application_id` |
| `404` | `APP_001` | `application_id` does not exist |
| `422` | `DPT_001` | `s3_key` format invalid or exceeds 500 chars |
| `422` | `DPT_003` | S3 object does not exist or access denied |
| `429` | `RATE_001` | Rate limit exceeded (5 extractions/min per user) |

---

### `GET /api/v1/dpt/jobs/{job_id}`
Poll extraction job status (long-polling supported via `?wait=30`).

**Authentication:** JWT required (same roles as above)

**Path Parameters:** `job_id: UUID`

**Query Parameters:** `wait: Optional[int] = 0` (max seconds to hold connection)

**Response Schema (200 OK):**
```python
class DPTJobStatusResponse(BaseModel):
    job_id: UUID
    status: Literal["pending", "processing", "success", "failed"]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress_percent: int  # 0-100, updated during processing
    error_message: Optional[str]  # Only if status == "failed"
    correlation_id: Optional[UUID]
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| `401` | `AUTH_001` | Missing or invalid JWT token |
| `403` | `AUTH_002` | User lacks permission for job's application |
| `404` | `DPT_002` | `job_id` not found |
| `410` | `DPT_008` | Job results expired (retention: 90 days) |

---

### `GET /api/v1/dpt/results/{job_id}`
Retrieve final extracted JSON data and confidence metrics.

**Authentication:** JWT required (roles: `broker`, `underwriter`, `admin`)

**Path Parameters:** `job_id: UUID`

**Response Schema (200 OK):**
```python
class DPTExtractionResult(BaseModel):
    job_id: UUID
    status: Literal["success"]
    extracted_data: Dict[str, Any]  # Schema varies by document_type
    confidence_score: Decimal  # 0.0000 to 1.0000
    confidence_threshold: Decimal  # Configured minimum (default 0.85)
    model_version: str  # e.g., "donut-noa-v1.2.3-prod"
    requires_manual_review: bool  # True if confidence < threshold
    extracted_at: datetime
    retention_expires_at: datetime  # Now + 5 years (FINTRAC)
```

**Error Responses:**
| HTTP Status | Error Code | Condition |
|-------------|------------|-----------|
| `401` | `AUTH_001` | Missing or invalid JWT token |
| `403` | `AUTH_002` | User lacks permission |
| `404` | `DPT_002` | `job_id` not found |
| `409` | `DPT_007` | Job not completed (status != "success") |
| `410` | `DPT_008` | Results archived per retention policy |

---

## 2. Models & Database

### ORM Model: `extraction_jobs`

**Table Name:** `extraction_jobs`

**Columns:**
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, default `gen_random_uuid()` | Job identifier |
| `application_id` | `UUID` | FK → `applications.id`, NOT NULL | Parent mortgage application |
| `document_type` | `VARCHAR(50)` | NOT NULL, CHECK IN (...) | Document category |
| `s3_key` | `VARCHAR(500)` | NOT NULL, UNIQUE | S3 object path |
| `filename` | `VARCHAR(255)` | NOT NULL | Original filename (PIPEDA audit) |
| `extracted_json` | `JSONB` | NULL, ENCRYPTED | AES-256 encrypted extraction output |
| `confidence` | `DECIMAL(5,4)` | NULL, CHECK 0-1 | Document-level confidence score |
| `model_version` | `VARCHAR(100)` | NULL | MLFlow model version tag |
| `status` | `VARCHAR(20)` | NOT NULL DEFAULT 'pending' | Job state |
| `error_message` | `TEXT` | NULL | Failure details (no PII) |
| `created_at` | `TIMESTAMP TZ` | NOT NULL DEFAULT NOW() | Audit trail |
| `updated_at` | `TIMESTAMP TZ` | NOT NULL DEFAULT NOW() | Last status update |
| `started_at` | `TIMESTAMP TZ` | NULL | Processing start |
| `completed_at` | `TIMESTAMP TZ` | NULL | Processing end |
| `created_by` | `UUID` | FK → `users.id` | Submitting user (FINTRAC) |

**Indexes:**
```sql
CREATE INDEX idx_extraction_jobs_app_id ON extraction_jobs(application_id);
CREATE INDEX idx_extraction_jobs_status ON extraction_jobs(status) WHERE status IN ('pending','processing');
CREATE INDEX idx_extraction_jobs_created_at ON extraction_jobs(created_at DESC);
CREATE INDEX idx_extraction_jobs_document_type ON extraction_jobs(document_type);
CREATE INDEX idx_extraction_jobs_confidence ON extraction_jobs(confidence) WHERE confidence IS NOT NULL;
CREATE UNIQUE INDEX idx_extraction_jobs_s3_key ON extraction_jobs(s3_key);  -- Idempotency
```

**Relationships:**
- Many-to-One: `extraction_jobs.application_id` → `applications.id`
- Many-to-One: `extraction_jobs.created_by` → `users.id`

**Encrypted Fields:**
- `extracted_json`: Encrypted using `pycryptodome` AES-256-GCM with key from `common/security.py::get_encryption_key()`. Encryption happens in application layer before INSERT.

**Audit Fields:**
- `created_at`, `updated_at` (auto-managed by SQLAlchemy event listeners)
- `created_by` (populated from JWT `sub` claim)

---

## 3. Business Logic

### Extraction Workflow State Machine

```
pending → processing → success
            ↓
          failed (terminal)
```

**Transitions:**
1. **pending → processing**: Worker picks job from queue
2. **processing → success**: Inference complete, confidence ≥ threshold
3. **processing → failed**: Inference error, S3 failure, or timeout
4. **processing → pending** (rollback): Worker crash, requeue after 5 min

### Confidence Scoring Algorithm

```python
def calculate_document_confidence(token_confidences: List[float]) -> Decimal:
    """
    Aggregate token-level confidence from Donut output.
    Rule: Arithmetic mean of all extracted field tokens.
    """
    if not token_confidences:
        return Decimal("0.0000")
    
    mean_confidence = sum(token_confidences) / len(token_confidences)
    # Round to 4 decimal places for precision
    return Decimal(str(mean_confidence)).quantize(Decimal("0.0001"))
```

**Threshold Matrix:**
| Document Type | Auto-Accept | Review Required | Reject |
|---------------|-------------|-----------------|--------|
| `noa` | ≥ 0.95 | 0.85-0.94 | < 0.85 |
| `t4/t4a` | ≥ 0.93 | 0.80-0.92 | < 0.80 |
| `bank_statement` | ≥ 0.90 | 0.75-0.89 | < 0.75 |
| `credit_report` | ≥ 0.92 | 0.80-0.91 | < 0.80 |
| `purchase_agreement` | ≥ 0.88 | 0.75-0.87 | < 0.75 |

### Model Selection Logic

```python
def get_model_version(document_type: str) -> str:
    """
    Query MLFlow registry for production model alias.
    Fallback to hardcoded version if MLFlow unavailable.
    """
    try:
        client = mlflow.MlflowClient()
        model_name = f"donut-{document_type.replace('_', '-')}"
        # Get model with 'production' alias
        mv = client.get_model_version_by_alias(model_name, "production")
        return f"{model_name}-{mv.version}"
    except mlflow.exceptions.MlflowException:
        # Fallback mapping (maintained in common/config.py)
        return settings.DPT_FALLBACK_MODELS[document_type]
```

### GPU Resource Management

- **Inference Timeout:** 60 seconds per document (configurable)
- **Batch Size:** 1 (single document per GPU to avoid resource contention)
- **Queue:** Arq (Redis) with priority queue (`high`: purchase_agreement, `normal`: noa, `low`: bank_statement)
- **Worker Pod Spec:** 
  - `nvidia.com/gpu: 1`
  - `memory: 8Gi`
  - `cpu: 2`
- **Scaler:** KEDA with Redis list length metric (scale at 10+ pending jobs)

---

## 4. Migrations

### Alembic Revision: `dpt_001_create_extraction_jobs`

```python
def upgrade():
    # Create ENUM types
    op.execute("CREATE TYPE documenttype AS ENUM ('t4', 't4a', 'noa', 'credit_report', 'bank_statement', 'purchase_agreement')")
    op.execute("CREATE TYPE extractionstatus AS ENUM ('pending', 'processing', 'success', 'failed')")
    
    # Create table
    op.create_table(
        "extraction_jobs",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("application_id", postgresql.UUID(), nullable=False),
        sa.Column("document_type", postgresql.ENUM(name="documenttype"), nullable=False),
        sa.Column("s3_key", sa.String(length=500), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("extracted_json", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", sa.DECIMAL(precision=5, scale=4), nullable=True),
        sa.Column("model_version", sa.String(length=100), nullable=True),
        sa.Column("status", postgresql.ENUM(name="extractionstatus"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("s3_key"),
    )
    
    # Create indexes
    op.create_index("idx_extraction_jobs_app_id", "extraction_jobs", ["application_id"])
    op.create_index("idx_extraction_jobs_status", "extraction_jobs", ["status"])
    op.create_index("idx_extraction_jobs_created_at", "extraction_jobs", ["created_at"], descending=True)
    op.create_index("idx_extraction_jobs_document_type", "extraction_jobs", ["document_type"])
    op.create_index("idx_extraction_jobs_confidence", "extraction_jobs", ["confidence"], postgresql_where=sa.text("confidence IS NOT NULL"))

def downgrade():
    op.drop_index("idx_extraction_jobs_confidence")
    op.drop_index("idx_extraction_jobs_document_type")
    op.drop_index("idx_extraction_jobs_created_at")
    op.drop_index("idx_extraction_jobs_status")
    op.drop_index("idx_extraction_jobs_app_id")
    op.drop_table("extraction_jobs")
    op.execute("DROP TYPE extractionstatus")
    op.execute("DROP TYPE documenttype")
```

### Data Migration Needs

- **Initial Seed:** Insert MLFlow model metadata into `model_registry` table (if separate)
- **Retention Policy:** Create PG cron job to archive `extracted_json` to encrypted S3 after 90 days, keep metadata for 5 years
- **Backfill:** None (new table)

---

## 5. Security & Compliance

### OSFI B-20 Implications
- **Data Integrity:** `extracted_json` must be immutable after `status='success'`. Implement database trigger to prevent UPDATE on success records.
- **Audit Trail:** All extraction attempts logged to `extraction_audit_log` table (separate from main table for performance).
- **GDS/TDS Source:** Income values extracted from NOA/T4 must include confidence metadata in underwriting calculation logs.

### FINTRAC Requirements
- **5-Year Retention:** `retention_expires_at` = `created_at` + 5 years. Archive to `s3://mortgage-underwriting-archive/extractions/` with encryption.
- **Immutable Records:** PostgreSQL `REVOKE UPDATE ON extraction_jobs FROM app_user;` after insert. Updates only allowed via privileged `updated_at` trigger.
- **Transaction Link:** `application_id` links extraction to mortgage transaction. Flag transactions > CAD $10,000 at underwriting layer, not DPT.
- **Access Logging:** Log all `GET /results/{job_id}` to `fintrac_access_log` with `user_id`, `timestamp`, `job_id`.

### CMHC Requirements
- **Precision:** Extracted `property_value` and `loan_amount` from purchase agreements must be stored as `Decimal` in `extracted_json`. Implement Pydantic validator to reject float values.
- **LTV Calculation:** Underwriting service must use extracted values with confidence ≥ 0.90 for CMHC insurance premium tier lookup.

### PIPEDA Data Handling
- **Encryption at Rest:** `extracted_json` encrypted with AES-256-GCM before INSERT. Key rotation every 90 days via `common/security.py::rotate_encryption_key()`.
- **SIN/DOB Handling:** 
  - Extracted SIN hashed with SHA-256 + salt (salt stored in `common/config.py`).
  - Original SIN never stored; hash used for cross-document correlation.
  - DOB stored as encrypted `YYYY-MM-DD` in `extracted_json`.
- **Data Minimization:** DPT service only extracts fields defined in `schemas/DocumentFieldDefinitions.yaml` per `document_type`. Reject PDFs with extraneous PII.
- **Logging:** 
  - NEVER log `s3_key`, `filename`, or any extracted field values.
  - Log only: `job_id`, `status`, `confidence`, `model_version`, `correlation_id`.
  - Use structlog with `drop_pii=True` processor.

### Authentication & Authorization
- **JWT Claims Required:** `sub` (user_id), `role`, `branch_id` (for brokers)
- **mTLS:** Enforced for inter-service calls (e.g., underwriting → DPT)
- **RBAC Matrix:**
  | Role | POST /extract | GET /jobs | GET /results |
  |------|---------------|-----------|--------------|
  | `borrower` | Own apps only | Own apps only | Denied |
  | `broker` | Own branch apps | Own branch apps | Own branch apps |
  | `underwriter` | All apps | All apps | All apps |
  | `admin` | All apps | All apps | All apps |

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy
```python
# modules/dpt/exceptions.py
class DPTException(AppException):
    """Base exception for DPT module"""
    pass

class DPTValidationError(DPTException):
    """Invalid input parameters"""
    http_status = 422
    error_code = "DPT_001"

class DPTJobNotFoundError(DPTException):
    """Extraction job does not exist"""
    http_status = 404
    error_code = "DPT_002"

class DPTS3AccessError(DPTException):
    """S3 permission or existence issue"""
    http_status = 403
    error_code = "DPT_003"

class DPTModelInferenceError(DPTException):
    """Donut model failure"""
    http_status = 500
    error_code = "DPT_004"

class DPTConfidenceTooLowError(DPTException):
    """Extraction quality below threshold"""
    http_status = 409
    error_code = "DPT_005"

class DPTDocumentTypeNotSupportedError(DPTException):
    """Document type not in fine-tuned models"""
    http_status = 400
    error_code = "DPT_006"

class DPTJobNotReadyError(DPTException):
    """Results requested before completion"""
    http_status = 409
    error_code = "DPT_007"

class DPTResultsExpiredError(DPTException):
    """Job exceeded 90-day retention"""
    http_status = 410
    error_code = "DPT_008"
```

### Structured Error Response
```json
{
  "detail": "Confidence 0.7423 below threshold 0.8500 for document_type 'bank_statement'",
  "error_code": "DPT_005",
  "metadata": {
    "job_id": "a1b2c3d4-e5f6-7890",
    "confidence": "0.7423",
    "threshold": "0.8500",
    "correlation_id": "f1e2d3c4-b5a6-7980"
  }
}
```

### Error Handling Flow
1. **Validation Errors:** Raised in `services.validate_extraction_request()` before job creation.
2. **S3 Errors:** Caught in worker, job marked `failed`, error_message sanitized (no PII).
3. **Model Errors:** Timeout after 60s, job marked `failed`, alert to #ml-ops Slack.
4. **Low Confidence:** Not a failure; `status='success'` but `requires_manual_review=True`.
5. **Expired Results:** Background job archives `extracted_json` to S3 after 90 days; DB record kept for 5 years.

---

## 7. Observability & Monitoring

### Prometheus Metrics
```python
# modules/dpt/metrics.py
EXTRACTIONS_SUBMITTED = Counter('dpt_extractions_submitted_total', 'Total extraction requests', ['document_type'])
EXTRACTION_DURATION = Histogram('dpt_extraction_duration_seconds', 'Time from submit to completion', buckets=[5, 10, 30, 60, 120, 300])
CONFIDENCE_DISTRIBUTION = Histogram('dpt_confidence_score', 'Extracted confidence scores', buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0])
EXTRACTION_FAILURES = Counter('dpt_extraction_failures_total', 'Failures by type', ['error_code'])
MANUAL_REVIEW_QUEUE = Gauge('dpt_manual_review_pending', 'Jobs awaiting manual review')
```

### OpenTelemetry Tracing
- Span per extraction: `dpt.extract.{document_type}`
- Attributes: `job_id`, `model_version`, `confidence`, `s3_bucket` (not key)
- Propagated `correlation_id` from request through worker to MLFlow logging

### Logging
```python
# structlog configuration
logger.info(
    "extraction_submitted",
    job_id=str(job.id),
    document_type=request.document_type,
    model_version=model_version,
    correlation_id=request.correlation_id,
    user_id=jwt.sub,
)
# NEVER log: s3_key, filename, extracted_data
```

---

## 8. Deployment & Scaling

### Kubernetes Resources
```yaml
# k8s/dpt-worker-deployment.yaml
spec:
  replicas: 3  # HPA managed
  template:
    spec:
      containers:
      - name: dpt-worker
        image: mortgage-underwriting/dpt-service:{{version}}
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: 8Gi
            cpu: 2
          limits:
            nvidia.com/gpu: 1
            memory: 10Gi
        env:
        - name: MLFLOW_TRACKING_URI
          valueFrom:
            secretKeyRef:
              name: mlflow-secrets
              key: tracking_uri
        - name: DPT_ENCRYPTION_KEY_ID
          value: "dpt-key-v1"  # Rotated via external secret operator
```

### Horizontal Pod Autoscaler
```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
spec:
  scaleTargetRef:
    name: dpt-worker
  triggers:
  - type: redis
    metadata:
      address: redis:6379
      listName: dpt:queue:pending
      listLength: "10"  # Scale when 10+ jobs pending
  minReplicaCount: 3
  maxReplicaCount: 20  # GPU quota limit
```

---

**WARNING:** This design assumes MLFlow is deployed separately with GPU node access. If MLFlow is unavailable, implement circuit breaker in `services.get_model_version()` to fallback to hardcoded versions from `config.py`.