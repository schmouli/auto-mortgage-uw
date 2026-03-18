# Document Processing Transformer (DPT) Service
Model: kimi-k2-thinking:cloud (complexity: reasoning)
Project: Canadian Mortgage Underwriting

# DPT Service Design Plan

**Feature Slug:** `dpt-service`  
**Module Path:** `modules/dpt/`  
**File:** `docs/design/dpt-service.md`

---

## 1. Endpoints

### `POST /api/v1/dpt/extract`
Submit a PDF document for asynchronous extraction.

**Authentication:** Authenticated (JWT) + application-level authorization (user must own `application_id`)

**Request Schema (multipart/form-data):**
```python
class DPTExtractRequest(BaseModel):
    application_id: UUID  # FK to applications table
    document_type: Literal["t4", "noa", "credit", "bank", "purchase"]
    file: UploadFile  # PDF only, max 10MB
```

**Response Schema (201 Created):**
```python
class DPTExtractResponse(BaseModel):
    job_id: UUID
    status: Literal["pending", "processing", "completed", "failed"]
    submitted_at: datetime
    estimated_completion_time: Optional[datetime]  # Based on queue depth
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 400 | DPT_003 | "Invalid file format: {mime_type}. Only application/pdf allowed" | Non-PDF upload |
| 422 | DPT_002 | "document_type must be one of: t4, noa, credit, bank, purchase" | Invalid document_type |
| 422 | DPT_007 | "File size exceeds 10MB limit" | File > 10MB |
| 404 | APP_001 | "Application {id} not found" | Invalid application_id |
| 403 | AUTH_002 | "Access denied to application {id}" | User lacks authorization |

---

### `GET /api/v1/dpt/jobs/{job_id}`
Poll extraction job status.

**Authentication:** Authenticated (JWT) + ownership check via `application_id` join

**Response Schema (200 OK):**
```python
class DPTJobStatusResponse(BaseModel):
    job_id: UUID
    status: Literal["pending", "processing", "completed", "failed"]
    document_type: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    confidence: Optional[Decimal]  # 0.00 to 1.00, 2 decimal places
    error_message: Optional[str]  # Only if status == failed
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 404 | DPT_001 | "Extraction job {job_id} not found" | Invalid job_id |
| 403 | AUTH_002 | "Access denied to job {job_id}" | User lacks ownership |

---

### `GET /api/v1/dpt/results/{job_id}`
Retrieve final extracted JSON data. **PII fields are encrypted at rest**.

**Authentication:** Authenticated (JWT) + ownership check

**Response Schema (200 OK):**
```python
class DPTResultsResponse(BaseModel):
    job_id: UUID
    application_id: UUID
    document_type: str
    extracted_data: Dict[str, Any]  # Decrypted JSON structure per doc type
    confidence: Decimal  # 0.00 to 1.00
    model_version: str  # e.g., "donut-noa-v1.3.2"
    extracted_at: datetime
    requires_manual_review: bool  # True if confidence < 0.95
```

**Document-Type Specific Schemas (simplified examples):**

*NOA Extraction:*
```json
{
  "line_15000_gross_income": "85000.00",
  "line_23600_net_income": "72000.00",
  "tax_year": "2023",
  "assessment_date": "2024-03-15"
}
```

*Bank Statement Extraction (FINTRAC flagged):*
```json
{
  "account_number": "ENCRYPTED_AES256",
  "institution": "RBC",
  "transactions": [
    {
      "date": "2024-01-15",
      "amount": "15000.00",
      "description": "WIRE TRANSFER INCOMING",
      "fintrac_flagged": true  # Auto-flagged if > $10,000
    }
  ]
}
```

**Error Responses:**
| HTTP Status | Error Code | Detail Pattern | Trigger Condition |
|-------------|------------|----------------|-------------------|
| 404 | DPT_001 | "Extraction job {job_id} not found" | Invalid job_id |
| 409 | DPT_005 | "Extraction not complete. Current status: {status}" | Status != completed |
| 403 | AUTH_002 | "Access denied to results {job_id}" | User lacks ownership |

---

## 2. Models & Database

### `extraction_jobs` Table
```sql
CREATE TABLE extraction_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    document_type VARCHAR(20) NOT NULL CHECK (document_type IN ('t4', 'noa', 'credit', 'bank', 'purchase')),
    s3_key VARCHAR(500) NOT NULL UNIQUE,  -- s3://bucket/prefix/{application_id}/{type}/{uuid}.pdf
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    confidence DECIMAL(5,4),  -- 0.0000 to 1.0000
    model_version VARCHAR(100) NOT NULL,
    extracted_json JSONB,  -- PII encrypted before storage
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Composite indexes for common query patterns
    CONSTRAINT fk_application FOREIGN KEY (application_id) REFERENCES applications(id)
);

CREATE INDEX idx_extraction_jobs_application_id ON extraction_jobs(application_id);
CREATE INDEX idx_extraction_jobs_status ON extraction_jobs(status);
CREATE INDEX idx_extraction_jobs_created_at ON extraction_jobs(created_at DESC);
CREATE INDEX idx_extraction_jobs_confidence ON extraction_jobs(confidence) WHERE status = 'completed';
```

### `extraction_model_versions` Table (MLFlow integration)
```sql
CREATE TABLE extraction_model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(100) NOT NULL,  -- e.g., "donut-noa"
    version VARCHAR(50) NOT NULL,  -- Semantic version from MLFlow
    mlflow_run_id VARCHAR(100) UNIQUE,  -- For experiment tracking
    is_active BOOLEAN NOT NULL DEFAULT false,
    confidence_threshold DECIMAL(5,4) NOT NULL DEFAULT 0.9500,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(model_name, version)
);

CREATE INDEX idx_model_versions_active ON extraction_model_versions(model_name) WHERE is_active = true;
```

---

## 3. Business Logic

### Extraction Pipeline Algorithm
```python
async def process_extraction(job_id: UUID):
    """
    Background worker task (Celery/RQ) for Donut inference
    """
    # 1. Retrieve job and lock for processing
    job = await get_extraction_job(job_id, for_update=True)
    
    # 2. Download PDF from S3 (temporary file, auto-deleted)
    pdf_path = await s3_client.download(job.s3_key, ttl=300)
    
    # 3. Select model based on document_type and active version
    model = await get_active_model(job.document_type)  # Query extraction_model_versions
    
    # 4. Run Donut inference (GPU-bound, timeout 120s)
    try:
        with gpu_lock():  # Semaphore for GPU resource management
            raw_json = await run_donut_inference(
                model_path=model.artifact_path,
                pdf_path=pdf_path,
                timeout=120
            )
    except GPUOutOfMemoryError:
        raise DPTProcessingError("GPU OOM, retrying with smaller batch")
    except TimeoutError:
        raise DPTProcessingError("Inference timeout after 120s")
    
    # 5. Validate schema and extract financial values as Decimal
    validated_json = parse_and_validate(job.document_type, raw_json)
    
    # 6. FINTRAC: Auto-flag transactions > $10,000 in bank statements
    if job.document_type == "bank":
        validated_json = flag_fintrac_transactions(validated_json)
    
    # 7. PIPEDA: Encrypt PII fields (SIN, DOB, account numbers)
    encrypted_json = encrypt_pii_fields(validated_json)
    
    # 8. Calculate confidence score (Donut's built-in + heuristics)
    confidence = calculate_weighted_confidence(
        donut_confidence=raw_json.get("confidence"),
        field_completeness=validated_json,
        financial_value_validation=validated_json
    )
    
    # 9. Update job record
    await update_extraction_job(
        job_id=job_id,
        status="completed" if confidence >= 0.80 else "failed",
        confidence=confidence,
        extracted_json=encrypted_json,
        error_message=None if confidence >= 0.80 else "Confidence below threshold"
    )
    
    # 10. Audit log (FINTRAC compliance)
    logger.info(
        "extraction_completed",
        job_id=str(job_id),
        application_id=str(job.application_id),
        document_type=job.document_type,
        confidence=float(confidence),
        model_version=model.version,
        fintrac_flagged=any(t.get("fintrac_flagged") for t in validated_json.get("transactions", []))
    )
```

### Confidence Scoring Formula
```python
def calculate_weighted_confidence(
    donut_confidence: float,
    field_completeness: Dict,
    financial_value_validation: Dict
) -> Decimal:
    """
    Weighted average: 40% Donut score, 30% field coverage, 30% financial validation
    """
    # Base model confidence (0-1)
    base = Decimal(str(donut_confidence))
    
    # Field completeness ratio (0-1)
    required_fields = get_required_fields_for_doc_type()
    completeness = Decimal(len(field_completeness)) / Decimal(len(required_fields))
    
    # Financial validation (0-1) - checks like valid date ranges, positive income, etc.
    validation_score = validate_financial_logic(financial_value_validation)
    
    final_score = (base * Decimal("0.40")) + (completeness * Decimal("0.30")) + (validation_score * Decimal("0.30"))
    return final_score.quantize(Decimal("0.0001"))
```

### Manual Review Thresholds
| Confidence Range | Action | UI Indicator |
|------------------|--------|--------------|
| ≥ 0.95 | Auto-accept, no review | Green |
| 0.80 - 0.94 | Flag for manual review, show diff | Yellow |
| < 0.80 | Reject, require manual data entry | Red |

---

## 4. Migrations

### New Tables
```python
# alembic/versions/xxx_create_extraction_tables.py

def upgrade():
    # Main extraction jobs table
    op.create_table(
        'extraction_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('application_id', sa.UUID(), nullable=False),
        sa.Column('document_type', sa.String(length=20), nullable=False),
        sa.Column('s3_key', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('confidence', sa.DECIMAL(precision=5, scale=4), nullable=True),
        sa.Column('model_version', sa.String(length=100), nullable=False),
        sa.Column('extracted_json', postgresql.JSONB(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('s3_key')
    )
    
    # Model versioning table for MLFlow integration
    op.create_table(
        'extraction_model_versions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('mlflow_run_id', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('confidence_threshold', sa.DECIMAL(precision=5, scale=4), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_name', 'version'),
        sa.UniqueConstraint('mlflow_run_id')
    )
    
    # Indexes for performance
    op.create_index('idx_extraction_jobs_application_id', 'extraction_jobs', ['application_id'])
    op.create_index('idx_extraction_jobs_status', 'extraction_jobs', ['status'])
    op.create_index('idx_extraction_jobs_created_at', 'extraction_jobs', ['created_at'], descending=True)
    op.create_index('idx_extraction_jobs_confidence', 'extraction_jobs', ['confidence'], 
                    postgresql_where=sa.text("status = 'completed'"))
    
    op.create_index('idx_model_versions_active', 'extraction_model_versions', ['model_name'],
                    postgresql_where=sa.text("is_active = true"))
```

### Data Migration (Seed Active Models)
```python
def seed_initial_models():
    """
    Seed active Donut model versions from MLFlow registry
    Run after deployment: uv run alembic upgrade head && uv run seed_dpt_models
    """
    models = [
        {"model_name": "donut-t4506", "version": "1.2.0", "mlflow_run_id": "run_456", "confidence_threshold": "0.9500"},
        {"model_name": "donut-noa", "version": "1.3.2", "mlflow_run_id": "run_789", "confidence_threshold": "0.9500"},
        {"model_name": "donut-credit", "version": "2.0.1", "mlflow_run_id": "run_101", "confidence_threshold": "0.9200"},
        {"model_name": "donut-bank", "version": "1.8.5", "mlflow_run_id": "run_202", "confidence_threshold": "0.9500"},
        {"model_name": "donut-purchase", "version": "1.0.0", "mlflow_run_id": "run_303", "confidence_threshold": "0.9300"},
    ]
    # Insert with is_active=true
```

---

## 5. Security & Compliance

### PIPEDA Data Handling
- **Encryption at Rest**: All `extracted_json` fields containing PII are encrypted using `common.security.encrypt_pii()` before DB storage. Encryption keys rotated every 90 days via Azure Key Vault.
- **Data Minimization**: Extract ONLY fields required for underwriting:
  - T4: Employer name, income boxes (14, 22, 24), YTD
  - NOA: Line 15000, 23600, tax year
  - Credit: Score, tradeline balances (no full account numbers)
  - Bank: Transaction amounts, dates, descriptions (mask account numbers to last 4)
  - Purchase: Price, closing date, address (no unit numbers)
- **Logging**: Never log extracted values, only metadata (`job_id`, `confidence`, `model_version`).

### FINTRAC Compliance
- **Immutable Audit Trail**: `extraction_jobs` table has no UPDATE/DELETE operations after creation. All status changes append new audit rows to `extraction_job_audit_log`.
- **$10K Transaction Flagging**: Bank statement parser auto-flags transactions ≥ CAD $10,000:
  ```python
  def flag_fintrac_transactions(transactions: List[Dict]) -> List[Dict]:
      for tx in transactions:
          amount = Decimal(tx["amount"])
          if amount >= Decimal("10000.00"):
              tx["fintrac_flagged"] = True
              tx["fintrac_reason"] = "Amount exceeds CAD 10,000 threshold"
              # Log for FINTRAC reporting
              logger.info("fintrac_transaction_flagged", job_id=..., amount=str(amount))
      return transactions
  ```
- **5-Year Retention**: `extraction_jobs` records are soft-deleted (archived to `extraction_jobs_archive` table) and retained for 5 years per FINTRAC regulations.

### OSFI B-20 Indirect Compliance
- Extracted income values (Line 15000, T4 Box 14) must be validated as Decimal with 2 decimal precision.
- All income extractions log `confidence` score; underwriter must manually verify if confidence < 0.95 before using in GDS/TDS calculations.
- **Audit Requirement**: When extracted income feeds into ratio calculations, log:
  ```python
  logger.info(
      "income_extraction_used_for_osfi",
      application_id=...,
      income_source="noa_line_15000",
      extracted_value="85000.00",
      confidence="0.9674",
      model_version="donut-noa-v1.3.2",
      manually_verified=(confidence < 0.95)
  )
  ```

### Authentication & Authorization
- **mTLS**: Service-to-S3 communication uses mutual TLS with certificate rotation.
- **JWT Claims Required**: `sub` (user_id), `application_ids` (list of UUIDs user can access).
- **Endpoint Guards**: 
  ```python
  async def verify_application_access(user: JWTUser, application_id: UUID):
      if application_id not in user.application_ids and "underwriter" not in user.roles:
          raise AuthorizationError()
  ```

---

## 6. Error Codes & HTTP Responses

### Module-Specific Exceptions (`modules/dpt/exceptions.py`)
```python
class DPTBaseException(AppException):
    module_code = "DPT"

class ExtractionJobNotFoundError(DPTBaseException):
    http_status = 404
    error_code = "DPT_001"
    message_template = "Extraction job {resource_id} not found"

class InvalidDocumentTypeError(DPTBaseException):
    http_status = 422
    error_code = "DPT_002"
    message_template = "document_type must be one of: t4, noa, credit, bank, purchase"

class InvalidFileFormatError(DPTBaseException):
    http_status = 400
    error_code = "DPT_003"
    message_template = "Invalid file format: {detail}. Only application/pdf allowed"

class ExtractionFailedError(DPTBaseException):
    http_status = 409
    error_code = "DPT_004"
    message_template = "Extraction failed: {detail}"

class ExtractionNotCompleteError(DPTBaseException):
    http_status = 409
    error_code = "DPT_005"
    message_template = "Extraction not complete. Current status: {detail}"

class ConfidenceThresholdError(DPTBaseException):
    http_status = 409
    error_code = "DPT_006"
    message_template = "Confidence {confidence} below threshold {threshold}. Manual review required."

class GPUResourceExhaustedError(DPTBaseException):
    http_status = 503
    error_code = "DPT_007"
    message_template = "GPU resources temporarily unavailable. Retry in {retry_after}s"
    headers = {"Retry-After": "30"}
```

### Structured Error Response Format
All errors return JSON consistent with project conventions:
```json
{
  "detail": "Extraction job 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "DPT_001",
  "module": "dpt",
  "timestamp": "2024-01-15T14:30:00Z",
  "correlation_id": "req_abc123"
}
```

### Error Handling Matrix
| Error Scenario | Exception Class | Retry Strategy | Alert Channel |
|----------------|-----------------|----------------|---------------|
| S3 download timeout | DPTProcessingError | Exponential backoff (3x) | Slack #dpt-alerts |
| GPU OOM | GPUResourceExhaustedError | Queue to dead-letter after 5x | PagerDuty Critical |
| Donut model crash | ExtractionFailedError | No retry (deterministic) | Sentry error |
| Confidence < 0.80 | ConfidenceThresholdError | Manual intervention | UI notification |
| Invalid PDF structure | InvalidFileFormatError | No retry | User-facing message |

---

## Additional Implementation Notes

### GPU Resource Allocation
- Use `asyncio.Semaphore(value=2)` per GPU instance to limit concurrent inferences.
- Queue depth metric exposed at `/metrics` for Prometheus autoscaling.
- Fallback to CPU inference if GPU unavailable (with 10x timeout multiplier).

### MLFlow Integration
- Model promotion workflow: Staging → Production (sets `is_active=true`) → Archived.
- A/B testing support: 10% traffic to new model version via `extraction_model_versions` weight column.
- Model performance dashboard tracks confidence drift; auto-rollback if drift > 5%.

### S3 Key Structure
```
s3://{bucket}/extractions/{environment}/{application_id}/{document_type}/{job_id}.pdf
```
- Lifecycle policy: Move to Glacier after 1 year, delete after 5 years (FINTRAC retention).
- Server-side encryption: AES-256 (S3-managed keys).

### Observability
- **Logs**: `structlog` with `correlation_id`, `job_id`, `model_version`, `confidence`.
- **Traces**: OpenTelemetry spans for each pipeline stage (download, inference, encrypt, store).
- **Metrics**:
  - `dpt_extraction_duration_seconds` (histogram)
  - `dpt_confidence_score` (gauge)
  - `dpt_fintrac_flagged_total` (counter)
  - `dpt_gpu_queue_depth` (gauge)