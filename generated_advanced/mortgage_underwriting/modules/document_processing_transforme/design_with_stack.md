# Design: Document Processing Transformer (DPT) Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Document Processing Transformer (DPT) Service Design Plan

**Feature Slug:** `dpt-service`  
**Module Path:** `modules/dpt_service/`  
**Design Doc:** `docs/design/dpt-service.md`

---

## 1. Endpoints

### 1.1 Submit Extraction Job
```http
POST /api/v1/dpt/extract
```

**Auth:** Authenticated (borrower, broker, or underwriter)

**Request Schema (`schemas.ExtractRequest`):**
```python
{
  "application_id": UUID,  # FK to mortgage_applications.id
  "document_type": Enum["t4506", "noa", "credit", "bank", "purchase"],  # Required
  "s3_key": str,  # S3 object key (e.g., "uploads/{app_id}/t4506_2023.pdf")
  "filename": str  # Original filename for audit logging
}
```

**Response Schema (`schemas.ExtractResponse`):**
```python
{
  "job_id": UUID,
  "status": Enum["pending", "processing", "completed", "failed"],
  "estimated_processing_time_seconds": int,
  "created_at": datetime
}
```

**Error Responses:**
| HTTP | Error Code | Condition |
|------|------------|-----------|
| 400 | DPT_002 | Missing required field or invalid document_type |
| 403 | DPT_006 | User does not own the referenced application_id |
| 404 | DPT_001 | application_id not found |
| 422 | DPT_002 | s3_key format validation failed (must match `^uploads/[0-9a-f-]+/[^/]+\.pdf$`) |
| 500 | DPT_003 | S3 presigned URL generation failed |

---

### 1.2 Poll Job Status
```http
GET /api/v1/dpt/jobs/{job_id}
```

**Auth:** Authenticated

**Response Schema (`schemas.JobStatusResponse`):**
```python
{
  "job_id": UUID,
  "status": Enum["pending", "processing", "completed", "failed"],
  "document_type": str,
  "confidence": Optional[Decimal],  # Null until completed
  "model_version": Optional[str],
  "created_at": datetime,
  "updated_at": datetime,
  "completed_at": Optional[datetime]
}
```

**Error Responses:**
| HTTP | Error Code | Condition |
|------|------------|-----------|
| 404 | DPT_001 | job_id not found or user lacks access |
| 410 | DPT_007 | Job results expired (retention: 30 days) |

---

### 1.3 Retrieve Extraction Results
```http
GET /api/v1/dpt/results/{job_id}
```

**Auth:** Authenticated

**Response Schema (`schemas.ExtractionResult`):**
```python
{
  "job_id": UUID,
  "application_id": UUID,
  "document_type": str,
  "extracted_data": dict,  # Structured fields per document_type
  "confidence": Decimal,  # 0.00 - 1.00
  "confidence_level": Enum["high", "medium", "low"],
  "model_version": str,  # MLFlow model version (e.g., "donut-noa@v3.2")
  "validation_warnings": List[str],  # e.g., ["Line 15000 missing", "Low confidence on employer name"]
  "created_at": datetime
}
```

**Document-Type Specific Payloads:**
- **t4506**: `{employer_name: str, income: Decimal, deductions: Decimal, ytd: Decimal, tax_year: int}`
- **noa**: `{line_15000: Decimal, line_23600: Decimal, tax_year: int}`
- **credit**: `{score: int, tradelines: List[dict], inquiries: int, collections: List[dict]}`
- **bank**: `{account_number_hash: str, transactions: List[dict], opening_balance: Decimal, closing_balance: Decimal}`
- **purchase**: `{purchase_price: Decimal, closing_date: date, property_address: dict}`

**Error Responses:**
| HTTP | Error Code | Condition |
|------|------------|-----------|
| 404 | DPT_001 | job_id not found |
| 409 | DPT_003 | Extraction failed (see detail for error message) |
| 410 | DPT_007 | Results expired |

---

## 2. Models & Database

### 2.1 `extractions` Table (`models.Extraction`)

```python
class Extraction(Base):
    __tablename__ = "extractions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("mortgage_applications.id"), nullable=False, index=True)
    document_type = Column(String(20), nullable=False, index=True)  # t4506, noa, credit, bank, purchase
    s3_key = Column(String(500), nullable=False)  # Immutable audit trail
    filename = Column(String(255), nullable=False)  # Original filename
    
    # Encrypted JSONB storage for PIPEDA compliance
    extracted_json = Column(LargeBinary, nullable=True)  # AES-256 encrypted JSON string
    confidence = Column(Numeric(precision=5, scale=4), nullable=True)  # 0.0000 to 1.0000
    model_version = Column(String(100), nullable=True)  # MLFlow model identifier
    
    status = Column(String(20), nullable=False, index=True, default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)  # Only populated on failure
    
    # Audit fields (FINTRAC 5-year retention)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, onupdate=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    application = relationship("MortgageApplication", back_populates="extractions")
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index("idx_extractions_app_doc", "application_id", "document_type"),
        Index("idx_extractions_status_created", "status", "created_at"),
        CheckConstraint("confidence BETWEEN 0.0 AND 1.0", name="chk_confidence_range"),
    )
```

### 2.2 `extraction_validation_warnings` Table (Optional Extension)

```python
class ExtractionValidationWarning(Base):
    __tablename__ = "extraction_validation_warnings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey("extractions.id"), nullable=False, index=True)
    warning_code = Column(String(50), nullable=False)  # e.g., "MISSING_FIELD", "LOW_CONFIDENCE"
    field_path = Column(String(200), nullable=True)  # JSON path to affected field
    message = Column(String(500), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
```

---

## 3. Business Logic

### 3.1 Async Processing Flow

```python
# services.py
class DPTService:
    CONFIDENCE_THRESHOLDS = {
        "high": Decimal("0.95"),
        "medium": Decimal("0.85"),
        "low": Decimal("0.70")  # Below this = manual review required
    }
    
    MODEL_MAPPING = {
        "t4506": "donut-t4506@v2.1",
        "noa": "donut-noa@v3.2",
        "credit": "donut-credit@v4.0",
        "bank": "donut-bank@v5.1",
        "purchase": "donut-purchase@v1.8"
    }
    
    async def submit_extraction(self, request: ExtractRequest, user_id: UUID) -> ExtractResponse:
        # 1. Validate application ownership
        # 2. Verify S3 key exists and is PDF (< 10MB)
        # 3. Create extraction record with status="pending"
        # 4. Trigger celery task: process_extraction.delay(job_id)
        # 5. Return job_id with estimated time (based on doc_type and queue depth)
    
    @celery.task(bind=True, max_retries=2)
    def process_extraction(self, job_id: UUID):
        # 1. Fetch extraction record, update status="processing"
        # 2. Download PDF from S3 to temp file
        # 3. Load Donut model from MLFlow (GPU allocation)
        # 4. Run inference with timeout (120s)
        # 5. Parse JSON output, calculate confidence score
        # 6. Encrypt extracted_json with AES-256 (PIPEDA)
        # 7. Update extraction record: status, confidence, model_version, extracted_json
        # 8. If confidence < 0.70, create validation warnings
        # 9. On failure: update status="failed", log error (no PII), retry twice
        # 10. Delete temp file
```

### 3.2 Confidence Scoring Algorithm

```python
def calculate_confidence(raw_donut_output: dict) -> Decimal:
    """
    Weighted average across extracted fields:
    - Fields with high cardinality (names, addresses): 0.95 weight
    - Numeric fields with validation: 1.00 weight
    - Optional fields: 0.50 weight
    """
    field_confidences = []
    for field, value in raw_donut_output.items():
        if field in ["employer_name", "property_address"]:
            field_confidences.append(Decimal("0.95") * value.get("confidence", 0.5))
        elif field in ["income", "line_15000", "score"]:
            # Validate numeric ranges
            field_confidences.append(Decimal("1.00") * value.get("confidence", 0.5))
        else:
            field_confidences.append(Decimal("0.50") * value.get("confidence", 0.5))
    
    if not field_confidences:
        return Decimal("0.0")
    
    avg_confidence = sum(field_confidences) / len(field_confidences)
    return Decimal(str(round(min(avg_confidence, Decimal("1.0")), 4)))
```

### 3.3 GPU Resource Management

```python
# GPU allocation pool (singleton)
class GPUManager:
    MAX_CONCURRENT_MODELS = 2  # Based on GPU memory (A100 40GB)
    MODEL_MEMORY_MB = {
        "donut-t4506": 1800,
        "donut-noa": 1800,
        "donut-credit": 2200,
        "donut-bank": 2500,
        "donut-purchase": 1600
    }
    
    async def acquire_gpu_slot(self, model_version: str) -> bool:
        # Check current GPU memory usage
        # Queue request if at capacity
        # Timeout after 300s
```

---

## 4. Migrations

### 4.1 New Table: `extractions`
```sql
CREATE TABLE extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES mortgage_applications(id) ON DELETE CASCADE,
    document_type VARCHAR(20) NOT NULL CHECK (document_type IN ('t4506', 'noa', 'credit', 'bank', 'purchase')),
    s3_key VARCHAR(500) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    extracted_json BYTEA,  -- Encrypted
    confidence NUMERIC(5,4) CHECK (confidence BETWEEN 0.0 AND 1.0),
    model_version VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID NOT NULL REFERENCES users(id)
);

CREATE INDEX idx_extractions_application_id ON extractions(application_id);
CREATE INDEX idx_extractions_document_type ON extractions(document_type);
CREATE INDEX idx_extractions_status_created ON extractions(status, created_at);
CREATE INDEX idx_extractions_app_doc ON extractions(application_id, document_type);
```

### 4.2 New Table: `extraction_validation_warnings` (Optional)
```sql
CREATE TABLE extraction_validation_warnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extraction_id UUID NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
    warning_code VARCHAR(50) NOT NULL,
    field_path VARCHAR(200),
    message VARCHAR(500) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_warnings_extraction_id ON extraction_validation_warnings(extraction_id);
```

### 4.3 Data Migration
- **None required** for new tables
- **Future migration**: When adding new document types, update CHECK constraints via `ALTER TABLE`

---

## 5. Security & Compliance

### 5.1 PIPEDA Data Handling
- **Encryption at Rest**: `extracted_json` field encrypted with AES-256-GCM before storage
  - Encryption key: Derived from `application_id` + master key (KMS)
  - IV: Random 12 bytes, prepended to ciphertext
- **Data Minimization**: Only extract fields required for underwriting
- **Log Sanitization**: Strip all PII from structlog output
  - **NEVER log**: SIN, DOB, account numbers, income values
  - **Log only**: job_id, document_type, confidence, status
- **Response Filtering**: `extracted_data` only returned to authenticated users with application ownership

### 5.2 FINTRAC Audit Trail
- **Immutable Records**: `extractions` table rows never deleted or modified
- **5-Year Retention**: Automatic archival to Glacier after 5 years
- **Created By**: Every extraction linked to user who submitted it
- **Document Provenance**: `s3_key` and `filename` preserved permanently

### 5.3 OSFI B-20 Indirect Compliance
- **Income Validation**: Extracted income values (Line 15000, T4 income) flagged with confidence scores
- **Manual Review Trigger**: If confidence < 0.85, underwriter must verify income before GDS/TDS calculation
- **Audit Log**: All income extractions logged with correlation_id for downstream underwriting audit

### 5.4 Authentication & Authorization
- **All endpoints**: JWT authentication required
- **Ownership Check**: `application_id` must belong to user's org/role
- **mTLS**: Service-to-S3 communication uses mTLS for bucket access
- **Rate Limiting**: 10 submissions/minute per user (prevent queue flooding)

---

## 6. Error Codes & HTTP Responses

```python
# exceptions.py
class DPTJobNotFoundError(AppException):
    """Extraction job not found or access denied"""
    status_code = 404
    error_code = "DPT_001"
    message_template = "Extraction job {job_id} not found"

class DPTValidationError(AppException):
    """Invalid request payload"""
    status_code = 422
    error_code = "DPT_002"
    message_template = "Validation failed: {detail}"

class DPTExtractionFailedError(AppException):
    """Donut inference or processing failed"""
    status_code = 409
    error_code = "DPT_003"
    message_template = "Extraction failed after {retry_count} attempts: {reason}"

class DPTDocumentTypeNotSupportedError(AppException):
    """Unsupported document type for extraction"""
    status_code = 400
    error_code = "DPT_004"
    message_template = "Document type '{doc_type}' not supported"

class DPTS3AccessError(AppException):
    """S3 object access failure"""
    status_code = 500
    error_code = "DPT_005"
    message_template = "Failed to access S3 key: {s3_key}"

class DPTPermissionDeniedError(AppException):
    """User lacks permission for application"""
    status_code = 403
    error_code = "DPT_006"
    message_template = "Access denied to application {application_id}"

class DPTResultsExpiredError(AppException):
    """Extraction results past retention period"""
    status_code = 410
    error_code = "DPT_007"
    message_template = "Extraction results expired after 30 days"
```

---

## 7. Additional Infrastructure Requirements

### 7.1 Celery Configuration
```python
# celeryconfig.py
broker_url = "redis://redis:6379/0"  # Or RabbitMQ for production
result_backend = "db+postgresql://postgres:5432/mortgage_underwriting"
task_serializer = "json"
result_serializer = "json"
task_time_limit = 300  # 5 minutes max per extraction
worker_prefetch_multiplier = 1  # Fair distribution
worker_max_tasks_per_child = 10  # Memory leak prevention
```

### 7.2 MLFlow Integration
```python
# MLFlow Model Registry Setup
# Models stored in: s3://mortgage-mlflow/donut-models/
# Each model version tagged with:
#   - validation_accuracy: float
#   - avg_inference_time_ms: int
#   - gpu_memory_mb: int

def load_donut_model(model_version: str) -> DonutModel:
    model_uri = f"models:/{model_version}"
    model = mlflow.pyfunc.load_model(model_uri)
    return model.unwrap_python_model()
```

### 7.3 GPU Resource Pool (Kubernetes)
```yaml
# deployment.yaml
resources:
  limits:
    nvidia.com/gpu: 1
  requests:
    nvidia.com/gpu: 1

# HPA based on queue length
autoscaling:
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: External
      external:
        metricName: celery_queue_length
        targetValue: 5
```

---

## 8. Testing Strategy

### 8.1 Unit Tests (`tests/unit/test_dpt_service.py`)
- Mock S3 and Donut model
- Test confidence calculation logic
- Test encryption/decryption round-trip
- Test validation warning generation

### 8.2 Integration Tests (`tests/integration/test_dpt_integration.py`)
- Full flow: upload PDF → submit → poll → retrieve results
- Test with real (anonymized) T4, NOA, credit report samples
- Verify PII encryption in database
- Test GPU resource contention handling

### 8.3 Performance Benchmarks
- Target: < 5s inference time per page on A100
- Throughput: 100 docs/minute with 5 workers
- Memory: < 3GB per model instance

---

## 9. Monitoring & Observability

### 9.1 Prometheus Metrics
```python
# metrics.py
EXTRACTIONS_SUBMITTED = Counter("dpt_extractions_submitted_total", "Total extraction jobs", ["document_type"])
EXTRACTION_DURATION = Histogram("dpt_extraction_duration_seconds", "Time per extraction", ["model_version"])
CONFIDENCE_SCORE = Histogram("dpt_confidence_score", "Distribution of confidence scores")
GPU_MEMORY_USAGE = Gauge("dpt_gpu_memory_mb", "GPU memory used by model", ["model_version"])
EXTRACTION_FAILURES = Counter("dpt_extraction_failures_total", "Failed extractions", ["document_type", "error_type"])
```

### 9.2 Structured Logging
```python
# In services.py
log.info(
    "extraction_submitted",
    job_id=str(job_id),
    application_id=str(request.application_id),
    document_type=request.document_type,
    s3_key=request.s3_key,
    correlation_id=correlation_id.get()
)
# NEVER log: extracted_data, filename with PII
```

---

## 10. Deployment Checklist

- [ ] Provision GPU nodes (A100 or T4) in Kubernetes cluster
- [ ] Deploy MLFlow server with S3 artifact store
- [ ] Set up Celery worker pool with GPU resource limits
- [ ] Configure S3 bucket policies for mTLS access
- [ ] Create KMS key for `extracted_json` encryption
- [ ] Pre-download Donut model weights to node cache
- [ ] Set up Prometheus alerts for queue depth > 50
- [ ] Configure 30-day TTL on `extractions` table (move to Glacier after)
- [ ] Run `pip-audit` on all ML dependencies (torch, transformers)

---