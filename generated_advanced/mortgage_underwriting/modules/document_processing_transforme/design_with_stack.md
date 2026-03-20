# Design: Document Processing Transformer (DPT) Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# Document Processing Transformer (DPT) Service Design Plan

## 1. Endpoints

### POST /api/v1/dpt/extract
Submit a PDF document for asynchronous extraction.

**Authentication:** Authenticated (JWT required, `underwriter` or `processor` role)

**Request Body Schema:**
```python
{
    "application_id": str,  # UUID of mortgage application
    "document_type": Literal["t4_t4a", "noa", "credit_report", "bank_statement", "purchase_agreement"],
    "s3_key": str,  # S3 object key (format: applications/{app_id}/documents/{uuid}.pdf)
    "priority": Optional[int] = 5  # 1-10, higher = faster processing
}
```

**Response Schema (201 Created):**
```python
{
    "job_id": str,  # UUID of extraction job
    "status": Literal["queued", "processing", "completed", "failed"],
    "estimated_processing_time_seconds": int,
    "created_at": datetime ISO8601
}
```

**Error Responses:**
- `400 Bad Request` - `DPT_002`: Invalid document_type or malformed s3_key
- `401 Unauthorized` - Missing or invalid JWT token
- `403 Forbidden` - Insufficient permissions (requires underwriter/processor role)
- `422 Unprocessable Entity` - `DPT_002`: application_id does not exist or s3_key not found
- `409 Conflict` - `DPT_003`: Document already submitted for this application_id + document_type combination

---

### GET /api/v1/dpt/jobs/{job_id}
Poll extraction job status.

**Authentication:** Authenticated (JWT required)

**Path Parameters:** `job_id: str` (UUID)

**Response Schema (200 OK):**
```python
{
    "job_id": str,
    "status": Literal["queued", "processing", "completed", "failed", "manual_review"],
    "document_type": str,
    "confidence": Optional[Decimal],  # Only present if completed
    "started_at": Optional[datetime],
    "completed_at": Optional[datetime],
    "error_code": Optional[str],  # DPT error code if failed
    "error_detail": Optional[str]  # Sanitized error message
}
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid JWT token
- `404 Not Found` - `DPT_001`: Extraction job not found
- `410 Gone` - `DPT_001`: Job records expired (retention policy)

---

### GET /api/v1/dpt/results/{job_id}
Retrieve structured extraction results.

**Authentication:** Authenticated (JWT required)

**Path Parameters:** `job_id: str` (UUID)

**Response Schema (200 OK):**
```python
{
    "job_id": str,
    "status": Literal["completed", "manual_review"],
    "document_type": str,
    "extracted_data": dict,  # Document-type specific schema
    "confidence": Decimal,  # Overall confidence score (0.0-1.0)
    "model_version": str,  # Donut model version (e.g., "donut-noa-v2.1.3")
    "validation_flags": List[str],  # Warnings e.g., ["low_confidence_field", "missing_required"]
    "created_at": datetime,
    "retention_expiry": datetime  # 5 years from created_at (FINTRAC)
}
```

**Error Responses:**
- `401 Unauthorized` - Missing or invalid JWT token
- `404 Not Found` - `DPT_001`: Extraction job not found or results not ready
- `409 Conflict` - `DPT_005`: Confidence below threshold, manual review required
- `410 Gone` - `DPT_001`: Results expired per retention policy

---

## 2. Models & Database

### Table: `dpt_extractions`

**Columns:**
| Column Name | Type | Constraints | Description |
|-------------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Extraction job ID |
| `application_id` | UUID | NOT NULL, FOREIGN KEY applications.id | Mortgage application |
| `document_type` | VARCHAR(32) | NOT NULL, CHECK IN (...), INDEX | Document category |
| `s3_key` | VARCHAR(512) | NOT NULL, UNIQUE per application | S3 object pointer |
| `extracted_json` | JSONB | NULL, ENCRYPTED at rest (AES-256) | Structured data output |
| `confidence` | DECIMAL(5,4) | NULL, CHECK (0.0 <= confidence <= 1.0) | Model confidence |
| `model_version` | VARCHAR(64) | NOT NULL | MLFlow model version |
| `status` | VARCHAR(24) | NOT NULL, INDEX | Job status |
| `error_code` | VARCHAR(16) | NULL | DPT error code if failed |
| `error_detail` | TEXT | NULL, ENCRYPTED | Sanitized error trace |
| `processing_started_at` | TIMESTAMPTZ | NULL | When processing began |
| `completed_at` | TIMESTAMPTZ | NULL, INDEX | When job finished |
| `validation_flags` | JSONB | NULL, DEFAULT '[]' | Array of validation warnings |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now(), INDEX | Audit field |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Audit field |

**Indexes:**
- `idx_dpt_extractions_app_id_doc_type` (application_id, document_type) - For duplicate detection
- `idx_dpt_extractions_status_completed` (status, completed_at) - For cleanup jobs
- `idx_dpt_extractions_created_retention` (created_at) - For FINTRAC retention queries

**Relationships:**
- Many-to-One: `application_id` → `applications.id` (ON DELETE CASCADE)
- No deletion allowed: Records retained for 5 years per FINTRAC

**Encryption Notes:**
- `extracted_json` contains PII (SIN, DOB, banking data) and must be encrypted at rest using `common/security.encrypt_pii()`
- `error_detail` may contain file paths or partial data - encrypt to prevent PII leakage

---

## 3. Business Logic

### Extraction Workflow State Machine
```
queued → processing → completed
   ↓          ↓           ↓
 failed   manual_review  (terminal)
```

**State Transitions:**
1. **queued**: Job submitted, validated, added to priority queue
2. **processing**: Worker dequeued, GPU allocated, Donut inference running
3. **completed**: Inference finished, confidence ≥ threshold, results stored
4. **manual_review**: Confidence < threshold OR validation_flags present
5. **failed**: Unrecoverable error (model crash, S3 timeout, validation error)

### Confidence Thresholds by Document Type
| Document Type | Minimum Confidence | Action Below Threshold |
|---------------|-------------------|------------------------|
| `t4_t4a` | 0.85 | Flag for manual review, log warning |
| `noa` | 0.90 | Reject extraction, require re-upload |
| `credit_report` | 0.80 | Accept with validation_flags |
| `bank_statement` | 0.75 | Accept with validation_flags |
| `purchase_agreement` | 0.90 | Reject extraction, require re-upload |

### Model Versioning Strategy (MLFlow)
- **Registry**: `models:/donut-{task}/{version}`
- **Version Format**: `{task}-v{major}.{minor}.{patch}` (e.g., `donut-noa-v2.1.3`)
- **A/B Testing**: 10% traffic to challenger model, 90% to champion
- **Fallback**: If model load fails, retry with previous stable version (max 2 attempts)
- **Audit**: Log `model_version` with every extraction for OSFI audit trails

### GPU Resource Allocation
- **Pool Size**: 4x NVIDIA T4 GPUs per node (configurable via `DPT_GPU_POOL_SIZE`)
- **Queue Prioritization**: Weighted by `priority` score and document_type criticality
  - `noa`, `purchase_agreement`: weight × 2.0
  - `t4_t4a`: weight × 1.5
  - Others: weight × 1.0
- **Timeout**: 300s per document (configurable), after which job marked failed
- **Auto-scaling**: Scale workers based on queue depth (target: < 5 min wait time)

### Validation Rules
- **SIN Extraction**: Must match regex `^\d{3}-\d{3}-\d{3}$`, hashed before storage
- **Income Fields**: Must be positive Decimal, log calculation breakdown for OSFI
- **Credit Score**: Must be integer 300-900, flag if outside range
- **Date Fields**: Must be valid dates, reject future dates for income docs
- **Bank Transactions**: If transaction amount > 10,000 CAD, add `fintrac_large_transaction` flag

---

## 4. Migrations

### New Table: `dpt_extractions`
```sql
CREATE TABLE dpt_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type VARCHAR(32) NOT NULL CHECK (document_type IN (
        't4_t4a', 'noa', 'credit_report', 'bank_statement', 'purchase_agreement'
    )),
    s3_key VARCHAR(512) NOT NULL,
    extracted_json JSONB,
    confidence DECIMAL(5,4) CHECK (confidence >= 0.0 AND confidence <= 1.0),
    model_version VARCHAR(64) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'queued',
    error_code VARCHAR(16),
    error_detail TEXT,
    processing_started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    validation_flags JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (application_id, document_type, s3_key)
);

CREATE INDEX idx_dpt_extractions_app_id_doc_type ON dpt_extractions(application_id, document_type);
CREATE INDEX idx_dpt_extractions_status_completed ON dpt_extractions(status, completed_at);
CREATE INDEX idx_dpt_extractions_created_retention ON dpt_extractions(created_at);
```

### New Alembic Migration: `2024_01_xx_create_dpt_extractions.py`
- **Dependencies**: Base migration, previous application table creation
- **Operations**: Create table, indexes, FK constraint
- **Post-migration**: Grant SELECT/INSERT to `underwriter` role; no UPDATE/DELETE per FINTRAC immutability

### Data Migration Needs
- **None** - New table only; no existing data to migrate

---

## 5. Security & Compliance

### FINTRAC Requirements
- **Immutability**: `extracted_json`, `error_detail` encrypted and never updated after creation
- **Large Transaction Flagging**: When bank statements show transactions > CAD 10,000, automatically set `validation_flags` containing `fintrac_reportable_transaction`
- **5-Year Retention**: `retention_expiry` field calculated as `created_at + INTERVAL '5 years'`
- **Audit Trail**: Every extraction job logged with `correlation_id`, `user_id`, and `application_id` via structlog

### PIPEDA Data Handling
- **Encryption at Rest**: `extracted_json` and `error_detail` encrypted using AES-256-GCM before storage; key rotation every 90 days
- **Data Minimization**: Only extract fields required for underwriting (income, SIN, credit score, property value); reject documents with extraneous PII
- **No Logging**: Strictly prohibit logging of SIN, DOB, account numbers, or transaction details; log only metadata (job_id, confidence, model_version)
- **SIN Hashing**: If SIN extracted, immediately hash with SHA256 before storing in `extracted_json`; use hash only for duplicate detection

### OSFI B-20 Implications
- **Income Verification**: Extracted income values from T4/T4A and NOA must be validated against declared income in application; discrepancies > 5% require manual review flag
- **Stress Test Audit**: When extraction provides income data, log full calculation breakdown: `gross_income`, `qualifying_rate`, `gds_ratio`, `tds_ratio` with timestamps

### Authentication & Authorization
- **Endpoints**: All endpoints require JWT authentication via `common/security.verify_token()`
- **Roles**: 
  - `underwriter`: Full access to submit, poll, retrieve
  - `processor`: Submit and poll only (cannot retrieve final results)
  - `admin`: Can access error_detail for debugging (PII still encrypted)
- **mTLS**: Service-to-S3 and service-to-MLFlow connections must use mutual TLS; certificates managed via `common/config.py`

---

## 6. Error Codes & HTTP Responses

| Exception Class | HTTP Status | Error Code | Message Pattern | Trigger Condition |
|-----------------|-------------|------------|-----------------|-------------------|
| `ExtractionJobNotFoundError` | 404 | `DPT_001` | "Extraction job {job_id} not found" | Invalid job_id or expired record |
| `DPTValidationError` | 422 | `DPT_002` | "{field}: {reason}" | Invalid document_type, malformed s3_key, or missing required fields |
| `ExtractionFailedError` | 500 | `DPT_003` | "Extraction failed: {detail}" | Donut model crash, S3 timeout, or unrecoverable error |
| `ModelUnavailableError` | 503 | `DPT_004` | "Model {version} unavailable" | MLFlow registry down or GPU allocation failure |
| `InsufficientConfidenceError` | 409 | `DPT_005` | "Confidence {score} below threshold {threshold}" | Confidence < minimum for document_type |
| `DuplicateSubmissionError` | 409 | `DPT_006` | "Document already submitted for application" | Unique constraint violation on (app_id, doc_type, s3_key) |

**Error Response Schema:**
```python
{
    "detail": str,  # Sanitized message
    "error_code": str,  # DPT_xxx code
    "correlation_id": str,  # For tracing
    "timestamp": datetime ISO8601
}
```

**Retry Policy:**
- `DPT_003` (ExtractionFailed): Retry up to 3 times with exponential backoff (2s, 4s, 8s)
- `DPT_004` (ModelUnavailable): Retry once after 30s, then fail
- `DPT_005` (InsufficientConfidence): No retry; flag for manual review

**Manual Review Queue:**
Jobs with status `manual_review` are surfaced in underwriter dashboard with:
- Original s3_key for visual verification
- Extracted data with low-confidence fields highlighted
- Option to accept/reject and provide corrected data (creates new extraction record, never updates original)