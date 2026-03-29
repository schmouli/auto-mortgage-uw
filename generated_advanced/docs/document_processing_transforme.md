# Document Processing Transformer (DPT) Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Document Processing Transformer (DPT) Service Design Plan

**Module Path:** `modules/dpt/`  
**Feature Slug:** `document-processing-transformer`  
**API Prefix:** `/api/v1/dpt`  
**Design Doc:** `docs/design/document-processing-transformer.md`

---

## 1. Endpoints

### 1.1 Submit PDF for Extraction
**`POST /api/v1/dpt/extract`**  
**Auth:** Authenticated (JWT, `underwriter` or `borrower` role)

**Request Schema (`schemas.ExtractionSubmitRequest`):**
```python
{
    "application_id": UUID,              # Required: Links to mortgage application
    "document_type": Enum["t4", "noa", "credit_report", "bank_statement", "purchase_agreement"],  # Required
    "s3_bucket": str,                    # Required: Source bucket name
    "s3_key": str,                       # Required: PDF object key (max 10MB)
    "callback_url": Optional[HttpUrl]    # Optional: Webhook for completion notification
}
```

**Response Schema (`schemas.ExtractionSubmitResponse`):**
```python
{
    "job_id": UUID,                      # Unique extraction job identifier
    "status": Enum["queued", "processing", "completed", "failed"],  # Initial status: "queued"
    "estimated_duration_seconds": int,   # Based on document type and GPU queue depth
    "submitted_at": datetime
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 400 | DPT_002 | "document_type must be one of: t4, noa, credit_report, bank_statement, purchase_agreement" |
| 400 | DPT_002 | "s3_key must end with .pdf and be ≤10MB" |
| 404 | DPT_001 | "Application {application_id} not found" |
| 422 | DPT_002 | "s3_bucket: field required" |
| 403 | AUTH_003 | "Insufficient permissions to access application" |

---

### 1.2 Poll Extraction Status
**`GET /api/v1/dpt/jobs/{job_id}`**  
**Auth:** Authenticated (same user who submitted the job)

**Response Schema (`schemas.ExtractionStatusResponse`):**
```python
{
    "job_id": UUID,
    "status": Enum["queued", "processing", "completed", "failed"],
    "progress_percent": int,             # 0-100, based on Donut inference steps
    "started_at": Optional[datetime],
    "completed_at": Optional[datetime],
    "error_code": Optional[str],         # Populated if status == "failed"
    "model_version": str                 # e.g., "donut-noa-v1.3.2"
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 404 | DPT_001 | "Extraction job {job_id} not found" |
| 403 | AUTH_003 | "Access denied to job {job_id}" |

---

### 1.3 Retrieve Structured Extraction Results
**`GET /api/v1/dpt/results/{job_id}`**  
**Auth:** Authenticated (same user who submitted the job)

**Response Schema (`schemas.ExtractionResultResponse`):**
```python
{
    "job_id": UUID,
    "status": "completed",               # Only returns 200 if completed
    "application_id": UUID,
    "document_type": str,
    "extracted_data": Dict[str, Any],    # PII-encrypted JSON structure (see encryption rules)
    "confidence_score": Decimal,         # 0.00 to 1.00, rounded to 2 decimal places
    "confidence_threshold_met": bool,    # True if ≥ configured minimum (e.g., 0.85)
    "pii_detected": List[str],           # Field names containing encrypted PII: ["sin", "dob", "account_number"]
    "model_version": str,
    "created_at": datetime,
    "retention_until": datetime          # FINTRAC: 5 years from created_at
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern |
|-------------|------------|----------------|
| 404 | DPT_001 | "Extraction job {job_id} not found or results not ready" |
| 409 | DPT_004 | "Extraction completed but confidence_score 0.72 < threshold 0.85" |
| 403 | AUTH_003 | "Access denied to results for job {job_id}" |

---

## 2. Models & Database

### 2.1 ORM Model: `ExtractionJob`
**Table Name:** `dpt_extraction_jobs`

| Column | Type | Constraints | Index | Description |
|--------|------|-------------|-------|-------------|
| `id` | UUID | PrimaryKey, default=gen_random_uuid() | PK | Job identifier |
| `application_id` | UUID | ForeignKey("applications.id", ondelete="CASCADE"), nullable=False | Composite idx | Underwriting application linkage |
| `document_type` | VARCHAR(32) | CheckConstraint in enum, nullable=False | Composite idx | Document classification |
| `s3_bucket` | VARCHAR(255) | nullable=False | - | Source S3 bucket |
| `s3_key` | VARCHAR(1024) | nullable=False, unique=True | Unique idx | S3 object key (encrypted) |
| `status` | VARCHAR(20) | CheckConstraint in ('queued','processing','completed','failed'), default='queued' | Single idx | Job state |
| `extracted_json` | JSONB | nullable=True | GIN idx | **Encrypted** structured output |
| `confidence_score` | DECIMAL(5,4) | CheckConstraint 0-1, nullable=True | Single idx | Model confidence |
| `model_version` | VARCHAR(50) | nullable=False | Single idx | MLFlow model tag |
| `mlflow_run_id` | VARCHAR(50) | nullable=True | - | Experiment tracking |
| `gpu_node_id` | VARCHAR(50) | nullable=True | - | Infrastructure telemetry |
| `error_log` | TEXT | nullable=True | - | Failure details (no PII) |
| `created_at` | TIMESTAMP | default=now(), nullable=False | Composite idx | FINTRAC audit trail |
| `updated_at` | TIMESTAMP | default=now(), onupdate=now(), nullable=False | - | Last status change |
| `retention_until` | TIMESTAMP | default=now() + interval '5 years', nullable=False | Single idx | FINTRAC retention |

**Indexes:**
- `idx_dpt_jobs_application_created` ON (application_id, created_at DESC)
- `idx_dpt_jobs_status_confidence` ON (status, confidence_score) WHERE status = 'completed'
- `idx_dpt_jobs_retention` ON (retention_until) WHERE retention_until < CURRENT_DATE

**Relationships:**
- Many-to-One: `application` → `Application` model (cascade delete)

---

### 2.2 PII Encryption Strategy
**PIPEDA Compliance:** All PII fields within `extracted_json` are encrypted at rest using AES-256-GCM.

**Encrypted Field Paths by Document Type:**
- **t4**: `$.employee_sin`, `$.employee_dob`, `$.employer_name`
- **noa**: `$.taxpayer_sin`, `$.line_15000` (income)
- **credit_report**: `$.consumer_sin`, `$.tradelines[*].account_number`
- **bank_statement**: `$.account_number`, `$.transactions[*].description` (contains merchant PII)
- **purchase_agreement**: `$.buyer_name`, `$.seller_name`

**Encryption Implementation:**
- Use `common/security.py:encrypt_pii()` before storing JSON
- Use `common/security.py:decrypt_pii()` when serving results
- Store encryption metadata (key_version, nonce) in separate `encryption_metadata` JSONB column

---

## 3. Business Logic

### 3.1 Extraction Orchestration Service (`services.DPTExtractionService`)

**Algorithm: Submit Extraction Job**
1. Validate `application_id` exists and user has access
2. Validate `document_type` against allowed enum
3. Verify S3 object exists and size ≤10MB via HEAD request
4. Generate unique `job_id` and presigned S3 URL for Donut worker
5. Publish message to GPU queue (e.g., AWS SQS + GPU ASG) with schema:
   ```python
   {
       "job_id": UUID,
       "s3_url": str,
       "document_type": str,
       "model_name": f"donut-{document_type}",
       "callback_topic": "dpt-extraction-results"
   }
   ```
6. Insert `ExtractionJob` record with status=`queued`
7. Log submission with `correlation_id` and `application_id` (no PII)

**Algorithm: Donut Inference Worker (GPU Node)**
1. Download PDF from presigned URL to tmpfs (RAM disk)
2. Load Donut model from MLFlow registry:
   ```python
   model = mlflow.pyfunc.load_model(f"models:/{model_name}/{model_version}")
   ```
3. Run inference with `return_scores=True` to get confidence
4. Post-process output:
   - Flatten nested Donut JSON into schema-aligned structure
   - Detect PII fields using regex patterns (e.g., `\d{3}-\d{3}-\d{3}` for SIN)
   - Encrypt detected PII fields individually
5. Calculate aggregate `confidence_score` = mean of field-level scores
6. Upload extracted JSON to temporary S3 bucket for durability
7. Publish result message to `callback_topic` with:
   ```python
   {
       "job_id": UUID,
       "status": "completed",
       "extracted_json_s3_key": str,
       "confidence_score": Decimal,
       "pii_detected": List[str],
       "gpu_node_id": str
   }
   ```

**Algorithm: Result Retrieval**
1. Verify job exists and user authorization
2. If `status != 'completed'`, return 409
3. If `confidence_score < CONFIDENCE_THRESHOLD` (config: 0.85), return 409 with error code DPT_004
4. Decrypt PII fields in `extracted_json` using `encryption_metadata`
5. Return response with `pii_detected` list for client awareness

---

### 3.2 Confidence Threshold Decision Matrix
| Document Type | Minimum Confidence | Auto-Retry Strategy | Manual Review Trigger |
|---------------|-------------------|---------------------|-----------------------|
| t4 | 0.85 | Yes, 1 retry with fallback model | Score < 0.70 |
| noa | 0.90 | No, immediate escalation | Score < 0.85 |
| credit_report | 0.80 | Yes, 2 retries with different GPU node | Score < 0.75 |
| bank_statement | 0.85 | Yes, 1 retry | Score < 0.70 |
| purchase_agreement | 0.90 | No, critical path escalation | Score < 0.85 |

---

### 3.3 State Machine Transitions
```
queued → processing (trigger: GPU worker picks up)
processing → completed (trigger: inference success AND confidence ≥ threshold)
processing → failed (trigger: inference error OR confidence < threshold AND retries exhausted)
queued → failed (trigger: S3 object not found or validation error)
```

---

## 4. Migrations

### 4.1 New Table: `dpt_extraction_jobs`
```sql
-- Create table with partitions by created_at (monthly) for FINTRAC retention
CREATE TABLE dpt_extraction_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type VARCHAR(32) NOT NULL CHECK (document_type IN ('t4','noa','credit_report','bank_statement','purchase_agreement')),
    s3_bucket VARCHAR(255) NOT NULL,
    s3_key VARCHAR(1024) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','processing','completed','failed')),
    extracted_json JSONB,
    confidence_score DECIMAL(5,4) CHECK (confidence_score BETWEEN 0 AND 1),
    model_version VARCHAR(50) NOT NULL,
    mlflow_run_id VARCHAR(50),
    gpu_node_id VARCHAR(50),
    error_log TEXT,
    encryption_metadata JSONB,  -- Stores nonce, key_version for PII fields
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    retention_until TIMESTAMP NOT NULL DEFAULT NOW() + INTERVAL '5 years'
) PARTITION BY RANGE (created_at);

-- Create initial partitions for next 12 months
CREATE TABLE dpt_extraction_jobs_y2024m01 PARTITION OF dpt_extraction_jobs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
-- ... repeat for 12 months
```

### 4.2 Indexes
```sql
CREATE INDEX idx_dpt_jobs_application_created ON dpt_extraction_jobs (application_id, created_at DESC);
CREATE INDEX idx_dpt_jobs_status_confidence ON dpt_extraction_jobs (status, confidence_score) WHERE status = 'completed';
CREATE INDEX idx_dpt_jobs_s3_key ON dpt_extraction_jobs (s3_key);
CREATE INDEX idx_dpt_jobs_retention ON dpt_extraction_jobs (retention_until) WHERE retention_until < CURRENT_DATE;
CREATE INDEX idx_dpt_jobs_extracted_json_gin ON dpt_extraction_jobs USING GIN (extracted_json);
```

### 4.3 Data Migration
- **None required** for new module. For existing applications, backfill `retention_until` on related tables if needed.

---

## 5. Security & Compliance

### 5.1 PIPEDA Data Handling
- **Encryption at Rest:** All `extracted_json` PII fields encrypted via AES-256-GCM before persistence. Encryption keys rotated every 90 days via `common/security.py`.
- **Data Minimization:** Only extract fields required for underwriting (configured per document type in `dpt/config.py`).
- **Logging:** NEVER log `extracted_json`, `s3_key`, or `application_id` in production logs. Use `job_id` and `correlation_id` only.
- **Response Filtering:** Hashed SIN (SHA256) may be returned for matching purposes, but never plaintext.

### 5.2 FINTRAC Audit Trail
- **Immutability:** `dpt_extraction_jobs` records are INSERT-only. Updates allowed only for `status`, `updated_at`. No DELETE operations permitted.
- **5-Year Retention:** `retention_until` column auto-calculated. Monthly cron job (`dpt/cleanup.py`) moves expired partitions to glacier storage.
- **Transaction Flagging:** If `document_type == 'bank_statement'` and extracted transaction amount > CAD 10,000, log FINTRAC flag in `applications.audit_log` table (via callback).

### 5.3 OSFI B-20 Relevance
- **Not Applicable:** DPT service does not calculate GDS/TDS. However, extracted income fields (Line 15000) must be validated for decimal precision (scale=2) before passing to underwriting module.

### 5.4 Authentication & Authorization
- **JWT Validation:** All endpoints require valid `Authorization: Bearer <jwt>` header.
- **Scope Check:** `dpt:submit`, `dpt:read` scopes required.
- **mTLS:** Service-to-service communication between FastAPI and GPU workers uses mutual TLS (`common/security.py:verify_mtls()`).

---

## 6. Error Codes & HTTP Responses

### Exception Hierarchy in `exceptions.py`

```python
class DPTException(AppException):
    """Base exception for DPT module"""
    pass

class DPTJobNotFoundError(DPTException):
    http_status = 404
    error_code = "DPT_001"

class DPTValidationError(DPTException):
    http_status = 422
    error_code = "DPT_002"

class DPTBusinessRuleError(DPTException):
    http_status = 409
    error_code = "DPT_003"

class DPTConfidenceThresholdError(DPTException):
    http_status = 409
    error_code = "DPT_004"

class DPTInfrastructureError(DPTException):
    http_status = 503
    error_code = "DPT_005"
```

### Error Mapping Table

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `DPTJobNotFoundError` | 404 | DPT_001 | "Extraction job {job_id} not found" | SELECT returns None |
| `DPTValidationError` | 422 | DPT_002 | "{field}: {reason}" | Pydantic validation fails |
| `DPTBusinessRuleError` | 409 | DPT_003 | "Document type {type} not supported for application status {status}" | Application not in draft/submitted state |
| `DPTConfidenceThresholdError` | 409 | DPT_004 | "Confidence {score} below threshold {threshold}" | Retrieval attempted with low confidence |
| `DPTInfrastructureError` | 503 | DPT_005 | "GPU queue unavailable, retry in {seconds}s" | SQS publish fails or no healthy GPU nodes |

### Retry Policy
- **Client Retry:** On 503, exponential backoff: 2s, 4s, 8s (max 3 attempts).
- **Server Retry:** On inference failure, retry once with fallback model version (e.g., `donut-noa-v1.2.1` if `v1.3.2` fails).

---

## 7. Infrastructure & Operations

### 7.1 GPU Resource Allocation
- **Auto Scaling Group:** GPU nodes (g5.xlarge) scale based on SQS queue depth (target: 10 messages per instance).
- **Model Caching:** EFS volume mounted at `/models` caches Donut models to avoid repeated MLFlow downloads.
- **Timeout:** Inference timeout = 300s per document. SQS message visibility timeout = 600s.

### 7.2 MLFlow Model Versioning
- **Registry Path:** `models:/donut-{document_type}/Production` for stable, `Staging` for canary.
- **Promotion Criteria:** Accuracy >95% on holdout set, confidence distribution within 0.1 std dev.
- **Model Schema:** Each model version logs input/output signature in MLFlow for validation.

### 7.3 Monitoring & Alerting
- **Prometheus Metrics:**
  - `dpt_jobs_submitted_total{document_type}`
  - `dpt_inference_duration_seconds{model_version}`
  - `dpt_confidence_score_histogram`
  - `dpt_pii_encrypted_fields_total`
- **Alerts:**
  - Confidence mean drops below 0.85 for >5% of jobs (P2)
  - GPU queue depth >100 (P1)
  - PII encryption failures >0 (P0 - page on-call)

---

## 8. Testing Strategy

### 8.1 Unit Tests (`tests/unit/test_dpt.py`)
- Mock S3 and MLFlow, test schema validation
- Test PII encryption/decryption round-trip
- Test confidence threshold logic

### 8.2 Integration Tests (`tests/integration/test_dpt_integration.py`)
- Spin up localstack S3, postgres, MLFlow tracking server
- Submit real PDF fixtures (anonymized) to `/extract`
- Poll until completion and validate decrypted JSON structure
- Test FINTRAC audit trail immutability

### 8.3 Performance Tests
- 100 concurrent submissions → measure queue throughput
- GPU inference latency p95 < 180s per document

---

**Design Approval Required By:** Architect, ML Lead, Compliance Officer  
**Implementation Estimate:** 3 sprints (Sprint 1: API & DB, Sprint 2: Donut integration, Sprint 3: Compliance & Ops)