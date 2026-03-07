# Design: Document Processing Transformer (DPT) Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Document Processing Transformer (DPT) Service Design Plan

**Project:** Canadian Mortgage Underwriting System  
**Module:** dpt (Document Processing Transformer)  
**Design Document:** docs/design/dpt-service.md  
**Version:** 1.0.0

---

## 1. Endpoints

### `POST /api/v1/dpt/extract`
Submit a PDF document for asynchronous extraction.

**Authentication:** JWT required (authenticated user)  
**Authorization:** User must have `read:documents` scope for the specified `application_id`

**Request Schema:**
```python
class DPTExtractionRequest(BaseModel):
    application_id: UUID  # FK to mortgage application
    document_type: Literal["t4_slip", "noa", "credit_report", "bank_statement", "purchase_agreement"]
    s3_key: str | None = None  # If file already uploaded to S3
    file: UploadFile | None = None  # Optional: upload file directly (max 10MB)
    
    model_config = {
        "json_schema_extra": {
            "examples": [{
                "application_id": "123e4567-e89b-12d3-a456-426614174000",
                "document_type": "noa",
                "s3_key": "uploads/applications/123e4567/noa_2023.pdf"
            }]
        }
    }
```

**Response Schema (202 Accepted):**
```python
class DPTExtractionResponse(BaseModel):
    job_id: UUID
    status: Literal["pending", "processing", "completed", "failed"]
    document_type: str
    created_at: datetime
    estimated_processing_time_seconds: int
    
    model_config = {
        "json_schema_extra": {
            "examples": [{
                "job_id": "456f7890-e89b-12d3-a456-426614174001",
                "status": "pending",
                "document_type": "noa",
                "created_at": "2024-01-15T14:30:00Z",
                "estimated_processing_time_seconds": 45
            }]
        }
    }
```

**Error Responses:**
| HTTP Status | Error Code | Detail | Trigger |
|-------------|------------|--------|---------|
| 400 | DPT_002 | "document_type must be one of: t4_slip, noa, credit_report, bank_statement, purchase_agreement" | Invalid enum value |
| 400 | DPT_002 | "Either s3_key or file must be provided" | Missing required file reference |
| 400 | DPT_002 | "File size exceeds 10MB limit" | File too large |
| 400 | DPT_002 | "application_id not found or access denied" | Authorization check failed |
| 401 | AUTH_001 | "Missing or invalid JWT token" | Authentication failed |
| 403 | AUTH_003 | "Insufficient permissions: read:documents required" | Scope missing |
| 422 | DPT_002 | "s3_key must start with 'uploads/' and end with '.pdf'" | Validation error |

---

### `GET /api/v1/dpt/jobs/{job_id}`
Poll the status of an extraction job.

**Authentication:** JWT required  
**Authorization:** User must own the associated `application_id`

**Response Schema:**
```python
class DPTJobStatusResponse(BaseModel):
    job_id: UUID
    status: Literal["pending", "processing", "completed", "failed"]
    progress_percentage: Decimal  # 0.00 to 100.00
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    confidence_score: Decimal | None  # Available when completed
    model_version: str | None  # e.g., "donut-noa-v1.2.3"
    
    model_config = {
        "json_schema_extra": {
            "examples": [{
                "job_id": "456f7890-e89b-12d3-a456-426614174001",
                "status": "processing",
                "progress_percentage": Decimal("65.50"),
                "started_at": "2024-01-15T14:30:05Z",
                "completed_at": None,
                "error_message": None,
                "confidence_score": None,
                "model_version": "donut-noa-v1.2.3"
            }]
        }
    }
```

**Error Responses:**
| HTTP Status | Error Code | Detail | Trigger |
|-------------|------------|--------|---------|
| 401 | AUTH_001 | "Missing or invalid JWT token" | Authentication failed |
| 403 | AUTH_003 | "Access denied to job" | User doesn't own application |
| 404 | DPT_001 | "Extraction job not found" | Invalid job_id |

---

### `GET /api/v1/dpt/results/{job_id}`
Retrieve the final structured extraction result (PII-filtered).

**Authentication:** JWT required  
**Authorization:** User must own the associated `application_id`

**Response Schema:**
```python
class DPTExtractionResultResponse(BaseModel):
    job_id: UUID
    application_id: UUID
    document_type: str
    status: Literal["completed"]
    confidence_score: Decimal  # 0.0000 to 1.0000
    model_version: str
    extracted_data: dict  # PII-filtered JSON structure
    pii_detected: bool  # True if SIN/DOB/banking found (encrypted in storage)
    created_at: datetime
    retention_expires_at: datetime  # FINTRAC 5-year retention
    
    model_config = {
        "json_schema_extra": {
            "examples": [{
                "job_id": "456f7890-e89b-12d3-a456-426614174001",
                "application_id": "123e4567-e89b-12d3-a456-426614174000",
                "document_type": "noa",
                "status": "completed",
                "confidence_score": Decimal("0.9432"),
                "model_version": "donut-noa-v1.2.3",
                "extracted_data": {
                    "line_15000_gross_income": "85000.00",
                    "line_23600_net_income": "72000.00",
                    "tax_year": "2023",
                    "assessment_date": "2024-03-15"
                },
                "pii_detected": True,
                "created_at": "2024-01-15T14:30:00Z",
                "retention_expires_at": "2029-01-15T14:30:00Z"
            }]
        }
    }
```

**Error Responses:**
| HTTP Status | Error Code | Detail | Trigger |
|-------------|------------|--------|---------|
| 401 | AUTH_001 | "Missing or invalid JWT token" | Authentication failed |
| 403 | AUTH_003 | "Access denied to result" | User doesn't own application |
| 404 | DPT_001 | "Extraction job not found" | Invalid job_id |
| 409 | DPT_003 | "Extraction not ready: status is processing" | Poll too early |
| 410 | DPT_005 | "Results expired: beyond 5-year retention" | FINTRAC retention expired |

---

## 2. Models & Database

### Table: `extractions`

**Table Name:** `dpt_extractions`  
**Purpose:** Immutable audit trail of all document extractions (FINTRAC compliance)

| Column | Type | Constraints | Index | Encrypted | Description |
|--------|------|-------------|-------|-----------|-------------|
| `id` | UUID | PRIMARY KEY, default gen_random_uuid() | - | No | Job identifier |
| `application_id` | UUID | NOT NULL, FK→applications.id | (application_id, created_at) | No | Mortgage application reference |
| `document_type` | VARCHAR(32) | NOT NULL, CHECK IN (...) | (document_type, status) | No | Document category enum |
| `s3_key` | TEXT | NOT NULL | (s3_key) UNIQUE | Yes | Encrypted S3 path |
| `extracted_json` | JSONB | - | GIN | Yes | Full encrypted extraction result |
| `confidence` | DECIMAL(5,4) | CHECK (confidence BETWEEN 0 AND 1) | (confidence) | No | Model confidence score |
| `model_version` | VARCHAR(64) | NOT NULL | (model_version) | No | MLFlow model identifier |
| `status` | VARCHAR(16) | NOT NULL, CHECK IN (...) | (status, created_at) | No | Job state |
| `error_message` | TEXT | - | - | No | Failure reason (no PII) |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() | (created_at DESC) | No | FINTRAC audit timestamp |
| `created_by` | UUID | NOT NULL | (created_by) | No | User ID from JWT |
| `retention_expires_at` | TIMESTAMPTZ | NOT NULL, default now() + interval '5 years' | (retention_expires_at) | No | FINTRAC retention deadline |

**Indexes:**
```sql
CREATE INDEX idx_extractions_app_created ON dpt_extractions(application_id, created_at DESC);
CREATE INDEX idx_extractions_status_created ON dpt_extractions(status, created_at) WHERE status IN ('pending','processing');
CREATE INDEX idx_extractions_confidence ON dpt_extractions(confidence) WHERE status = 'completed';
CREATE INDEX idx_extractions_retention ON dpt_extractions(retention_expires_at) WHERE retention_expires_at < NOW();
CREATE UNIQUE INDEX idx_extractions_s3_key ON dpt_extractions(s3_key);  -- Prevent duplicate processing
```

**Encryption Strategy:**
- `s3_key`: Encrypted with `encrypt_pii()` from `common.security` before storage
- `extracted_json`: Full JSON blob encrypted at rest using AES-256-GCM via `encrypt_pii()`
- Decryption only occurs in service layer; API responses filter out PII fields

---

### Table: `extraction_pii_cache` (Optional Performance Optimization)

**Table Name:** `dpt_extraction_pii_cache`  
**Purpose:** Hashed PII for duplicate detection without decryption (PIPEDA compliance)

| Column | Type | Constraints | Index | Description |
|--------|------|-------------|-------|-------------|
| `extraction_id` | UUID | PK, FK→extractions.id | - | Reference to parent record |
| `pii_hash` | VARCHAR(64) | NOT NULL | UNIQUE | SHA256 of concatenated PII fields |
| `pii_type` | VARCHAR(16) | NOT NULL | (pii_type, pii_hash) | Enum: sin, dob, account |
| `created_at` | TIMESTAMPTZ | NOT NULL | - | Audit timestamp |

**Note:** This table enables duplicate document detection without decrypting `extracted_json`. Hashes computed as `SHA256(normalized_pii_value + pepper)`.

---

## 3. Business Logic

### State Machine

```
pending → processing → completed
            ↓
          failed
```

**Transitions:**
- `pending→processing`: Celery worker picks up job (max 5 min queue time)
- `processing→completed`: Donut inference completes, confidence ≥ threshold
- `processing→failed`: Timeout, GPU OOM, model error, or confidence < threshold
- `completed→expired`: FINTRAC retention job marks after 5 years (soft delete)

### Processing Pipeline Algorithm

```python
async def process_extraction(job_id: UUID):
    # 1. Fetch job record (ROW LOCK)
    extraction = await get_extraction_for_update(job_id)
    
    # 2. Validate GPU availability
    if not await gpu_allocator.acquire_slot(timeout=30):
        raise DPTResourceError("No GPU capacity available")
    
    try:
        # 3. Download PDF from S3 (stream to temp file)
        pdf_path = await s3_client.download_encrypted(extraction.s3_key)
        
        # 4. Load Donut model (cached in GPU memory)
        model = await model_loader.get_model(extraction.model_version)
        
        # 5. Run inference with timeout
        with timeout(seconds=DOCUMENT_TYPE_TIMEOUTS[extraction.document_type]):
            result = await model.inference(pdf_path)
        
        # 6. Post-process and validate schema
        validated = DocumentValidator(extraction.document_type).validate(result)
        
        # 7. Compute aggregate confidence
        confidence = calculate_weighted_confidence(validated, model.version)
        
        # 8. PII detection and encryption
        pii_detected = detect_pii_fields(validated)
        encrypted_json = encrypt_pii(json.dumps(validated))
        
        # 9. Quality gate check
        threshold = CONFIDENCE_THRESHOLDS[extraction.document_type]
        if confidence < threshold:
            raise DPTInsufficientConfidenceError(
                f"Confidence {confidence} < threshold {threshold}"
            )
        
        # 10. Store results (immutable)
        await update_extraction_success(
            job_id, 
            encrypted_json=encrypted_json,
            confidence=confidence,
            pii_detected=pii_detected
        )
        
        # 11. Emit audit log (FINTRAC)
        audit_logger.info(
            "extraction_completed",
            job_id=job_id,
            application_id=extraction.application_id,
            document_type=extraction.document_type,
            model_version=extraction.model_version,
            confidence=confidence,
            pii_detected=pii_detected
        )
        
    except Exception as e:
        await handle_extraction_failure(job_id, e)
        raise
    finally:
        gpu_allocator.release_slot()
        cleanup_temp_files(pdf_path)
```

### Confidence Scoring Formula

```
confidence = Σ(field_confidence × field_weight) / Σ(field_weights)

Field Weights by Document Type:
- t4_slip: employment_income (0.4), ytd (0.3), employer (0.2), deductions (0.1)
- noa: line_15000 (0.5), line_23600 (0.3), tax_year (0.2)
- credit_report: score (0.4), tradelines (0.4), inquiries (0.2)
- bank_statement: transactions (0.5), balances (0.4), account_info (0.1)
- purchase_agreement: purchase_price (0.5), closing_date (0.3), address (0.2)
```

### Quality Gate Thresholds

| Document Type | Minimum Confidence | Max Processing Time | Retry Attempts |
|---------------|-------------------|---------------------|----------------|
| t4_slip | 0.85 | 60s | 3 |
| noa | 0.90 | 45s | 2 |
| credit_report | 0.80 | 90s | 3 |
| bank_statement | 0.75 | 120s | 3 |
| purchase_agreement | 0.90 | 30s | 2 |

### GPU Resource Allocation

```yaml
# Kubernetes Resource Requests/Limits
resources:
  requests:
    nvidia.com/gpu: 1
    memory: 8Gi
  limits:
    nvidia.com/gpu: 1
    memory: 12Gi

# Celery Worker Configuration
worker_concurrency: 1  # One GPU per worker
worker_prefetch_multiplier: 1
task_time_limit: 180  # Hard kill after 3 min
task_soft_time_limit: 150  # Soft timeout
```

---

## 4. Migrations

### Alembic Revision: `create_dpt_extractions_table`

```python
revision = 'dpt_001_create_extractions'
down_revision = None

def upgrade():
    # Create enum types
    op.execute("CREATE TYPE dpt_document_type AS ENUM ('t4_slip', 'noa', 'credit_report', 'bank_statement', 'purchase_agreement')")
    op.execute("CREATE TYPE dpt_extraction_status AS ENUM ('pending', 'processing', 'completed', 'failed')")
    
    # Main extractions table
    op.create_table(
        'dpt_extractions',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('application_id', sa.UUID(), nullable=False, index=True),
        sa.Column('document_type', sa.Enum('t4_slip', 'noa', 'credit_report', 'bank_statement', 'purchase_agreement', name='dpt_document_type'), nullable=False),
        sa.Column('s3_key', sa.Text(), nullable=False),
        sa.Column('extracted_json', postgresql.JSONB(), nullable=True),
        sa.Column('confidence', sa.DECIMAL(5, 4), nullable=True),
        sa.Column('model_version', sa.String(64), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', name='dpt_extraction_status'), nullable=False, index=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()'), index=True),
        sa.Column('created_by', sa.UUID(), nullable=False, index=True),
        sa.Column('retention_expires_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now() + interval '5 years'")),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('s3_key', name='uq_extractions_s3_key')
    )
    
    # Composite indexes
    op.create_index('idx_extractions_app_created', 'dpt_extractions', ['application_id', sa.text('created_at DESC')])
    op.create_index('idx_extractions_status_created', 'dpt_extractions', ['status', 'created_at'], 
                    postgresql_where=sa.text("status IN ('pending', 'processing')"))
    op.create_index('idx_extractions_confidence', 'dpt_extractions', ['confidence'], 
                    postgresql_where=sa.text("status = 'completed'"))
    op.create_index('idx_extractions_retention', 'dpt_extractions', ['retention_expires_at'], 
                    postgresql_where=sa.text("retention_expires_at < now()"))
    
    # GIN index for JSONB (for future metadata queries)
    op.create_index('idx_extractions_jsonb', 'dpt_extractions', ['extracted_json'], 
                    postgresql_using='gin')
    
    # PII cache table
    op.create_table(
        'dpt_extraction_pii_cache',
        sa.Column('extraction_id', sa.UUID(), primary_key=True),
        sa.Column('pii_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('pii_type', sa.Enum('sin', 'dob', 'account', name='dpt_pii_type'), nullable=False, index=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['extraction_id'], ['dpt_extractions.id'], ondelete='CASCADE')
    )
    op.create_index('idx_pii_cache_type_hash', 'dpt_extraction_pii_cache', ['pii_type', 'pii_hash'])

def downgrade():
    op.drop_table('dpt_extraction_pii_cache')
    op.drop_table('dpt_extractions')
    op.execute("DROP TYPE dpt_pii_type")
    op.execute("DROP TYPE dpt_extraction_status")
    op.execute("DROP TYPE dpt_document_type")
```

### Data Migration: Seed Model Versions

```python
# Insert supported model versions into config table
def seed_model_versions():
    op.execute("""
        INSERT INTO dpt_model_registry (version, document_type, parameters, gpu_memory_mb, confidence_threshold)
        VALUES 
        ('donut-t4506-v1.2.3', 't4_slip', 176000000, 6144, 0.85),
        ('donut-noa-v1.1.8', 'noa', 176000000, 6144, 0.90),
        ('donut-credit-v2.0.1', 'credit_report', 176000000, 7168, 0.80),
        ('donut-bank-v1.4.5', 'bank_statement', 176000000, 8192, 0.75),
        ('donut-purchase-v1.0.0', 'purchase_agreement', 176000000, 5120, 0.90)
    """)
```

---

## 5. Security & Compliance

### PIPEDA Compliance
- **Encryption at Rest:** `extracted_json` and `s3_key` encrypted with AES-256-GCM via `common.security.encrypt_pii()`
- **Data Minimization:** API responses filter out SIN, DOB, full account numbers. Only return masked values (e.g., "•••••1234")
- **PII Hashing:** SHA256 hashes stored in separate table for duplicate detection without decryption
- **Access Logging:** Every `GET /results/{job_id}` access logged with `correlation_id`, user_id, timestamp (no PII in logs)

### FINTRAC Requirements
- **Immutable Audit Trail:** `extractions` table has NO UPDATE permissions. All status changes insert new audit rows into `dpt_extraction_audit_log`
- **5-Year Retention:** `retention_expires_at` auto-calculated. Daily job moves expired records to cold storage (Glacier) with hash verification
- **Transaction Threshold:** If extracted `transaction_amount > 10000` from bank statements, auto-flag `fintrac_reporting_required = True` in linked application

### OSFI B-20 Integration
- Extracted income values (Line 15000, employment income) feed into GDS/TDS calculations in underwriting module
- Confidence threshold ensures data quality for regulatory calculations
- Audit log includes `confidence_score` to prove data reliability for stress test calculations

### Authentication & Authorization
```python
# FastAPI dependency
async def verify_document_access(
    job_id: UUID, 
    token: JWTToken = Depends(verify_token)
) -> bool:
    extraction = await get_extraction(job_id)
    if extraction.created_by != token.sub:
        # Check if user has admin:documents scope
        if "admin:documents" not in token.scopes:
            raise DPTAccessDeniedError()
    return True
```

### mTLS Service-to-Service
- DPT service verifies client certificates from underwriting API
- Certificate CN must match `service:underwriting` or `service:mlflow`
- Revocation list checked every 5 minutes via `common.security.verify_mtls()`

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy

```python
class DPTException(AppException):
    """Base exception for DPT module"""
    module_code = "DPT"

class DPTJobNotFoundError(DPTException):
    http_status = 404
    error_code = "DPT_001"
    message_pattern = "Extraction job '{job_id}' not found"

class DPTValidationError(DPTException):
    http_status = 422
    error_code = "DPT_002"
    message_pattern = "Validation failed: {field} - {reason}"

class DPTExtractionFailedError(DPTException):
    http_status = 409
    error_code = "DPT_003"
    message_pattern = "Extraction failed: {detail}"

class DPTInsufficientConfidenceError(DPTException):
    http_status = 409
    error_code = "DPT_004"
    message_pattern = "Confidence {actual} below threshold {threshold} for {doc_type}"

class DPTResultsExpiredError(DPTException):
    http_status = 410
    error_code = "DPT_005"
    message_pattern = "Results expired beyond FINTRAC retention period"

class DPTResourceError(DPTException):
    http_status = 503
    error_code = "DPT_006"
    message_pattern = "GPU resource unavailable: {detail}"

class DPTAccessDeniedError(DPTException):
    http_status = 403
    error_code = "DPT_007"
    message_pattern = "Access denied to extraction job"
```

### Error Response Format
All errors return consistent JSON:
```json
{
  "detail": "Extraction failed: Donut model OOM on GPU",
  "error_code": "DPT_003",
  "module": "dpt",
  "timestamp": "2024-01-15T14:35:12Z",
  "correlation_id": "9f3d8a7b-1c2d-4e5f-8a9b-2c3d4e5f6a7b",
  "request_id": "req_abc123def456"
}
```

### Retry Strategy
```python
# Celery task configuration
@celery.task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    autoretry_for=(DPTResourceError, DPTExtractionFailedError),
    throws=(DPTInsufficientConfidenceError, DPTValidationError)  # Don't retry these
)
def run_extraction(self, job_id: UUID):
    try:
        await process_extraction(job_id)
    except DPTResourceError as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 10)
```

---

## 7. Model Versioning & MLFlow Integration

### MLFlow Model Registry
```python
# In services.py
class ModelLoader:
    def __init__(self, tracking_uri: str):
        self.client = mlflow.MlflowClient(tracking_uri)
        self.cache = LRUCache(maxsize=3)  # Max 3 models in GPU memory
    
    async def get_model(self, version: str) -> DonutModel:
        if version not in self.cache:
            model_uri = self.client.get_model_version_download_uri("dpt", version)
            self.cache[version] = await load_donut_model(model_uri)
        return self.cache[version]
```

### Model Promotion Workflow
1. **Staging:** New model version registered with `stage="Staging"`
2. **Validation:** Process 100 historical docs, compare confidence distribution
3. **Production:** Promote via MLFlow API; DPT service auto-loads on next request
4. **Rollback:** If production confidence drops >5%, revert to previous version

---

## 8. Monitoring & Observability

### Prometheus Metrics
```python
# In routes.py
dpt_jobs_submitted = Counter('dpt_jobs_submitted_total', 'Total extraction jobs', ['document_type'])
dpt_jobs_completed = Counter('dpt_jobs_completed_total', 'Completed jobs', ['document_type', 'status'])
dpt_confidence_histogram = Histogram('dpt_confidence_score', 'Confidence distribution', ['model_version'])
dpt_gpu_memory = Gauge('dpt_gpu_memory_mb', 'GPU memory used')
dpt_processing_duration = Histogram('dpt_processing_seconds', 'Processing time', ['document_type'])
```

### Structured Logging
```python
# In services.py
logger.info(
    "extraction_started",
    job_id=job_id,
    application_id=application_id,
    document_type=document_type,
    model_version=model_version,
    gpu_id=gpu_allocator.current_device(),
    correlation_id=correlation_id.get()
)
# NEVER log: extracted_json, s3_key, or any PII fields
```

---

## 9. Deployment Considerations

### Infrastructure Requirements
- **GPU Node Pool:** AWS G4dn.xlarge (4 vCPU, 16GB RAM, NVIDIA T4)
- **Horizontal Scaling:** K8s HPA based on queue length (Celery metrics)
- **Cold Start:** Model pre-loading on pod startup (init container)
- **Graceful Shutdown:** 30s termination grace period to complete in-flight extractions

### Environment Variables (`.env.example`)
```bash
# DPT Service
DPT_MLFLOW_TRACKING_URI=https://mlflow.mortgage.internal
DPT_S3_BUCKET=mortgage-documents-prod
DPT_GPU_MEMORY_LIMIT_MB=14336  # T4 has 16GB, leave buffer
DPT_CONFIDENCE_THRESHOLD_T4_SLIP=0.85
DPT_CONFIDENCE_THRESHOLD_NOA=0.90
DPT_CONFIDENCE_THRESHOLD_CREDIT=0.80
DPT_CONFIDENCE_THRESHOLD_BANK=0.75
DPT_CONFIDENCE_THRESHOLD_PURCHASE=0.90

# Security
DPT_PII_ENCRYPTION_KEY_ID=arn:aws:kms:ca-central-1:123456789:key/dpt-pii-master
DPT_MTLS_CERT_PATH=/certs/dpt-server.pem
DPT_MTLS_KEY_PATH=/certs/dpt-server.key
```

---

## 10. Future Enhancements

- **Streaming Results:** WebSocket endpoint `/dpt/stream/{job_id}` for real-time progress
- **Human-in-the-Loop:** If confidence 0.70-0.80, route to manual review queue
- **Active Learning:** Low-confidence extractions auto-added to training set
- **Multi-language Support:** French T4/Relevé 1 forms with locale-specific models
- **Document Tampering Detection:** Add authenticity score using Donut's reconstruction error

---

**WARNING:** This design assumes Donut model inference is deterministic enough for financial regulatory use. If non-determinism is detected, implement checksum verification of extracted values against source PDF via digital signature validation.