Here is the documentation for the Document Processing Transformer (DPT) Service module.

### 1. API Documentation

**File:** `docs/api/document_processing_transformer.md`

```markdown
# Document Processing Transformer (DPT) Service API

This microservice handles the ingestion of mortgage-related documents (T4, NOA, Credit Reports) via S3, performs inference using fine-tuned Donut models, and returns structured JSON data.

**Note on PIPEDA Compliance:**
This service processes PII. All requests must be made over TLS. Extracted sensitive fields (SIN, DOB, Income) are returned in the response payload. It is the caller's responsibility to encrypt this data at rest and ensure it is not logged.

---

## POST /api/v1/document-processing/extract

Submits a document for processing. The service retrieves the PDF from S3, determines the appropriate fine-tuned model (T4, NOA, or Credit), and runs inference.

**Request:**
```json
{
  "s3_bucket": "mortgage-docs-prod",
  "s3_key": "borrowers/101/application_2026/t4_slip.pdf",
  "document_type": "T4",
  "correlation_id": "req_abc123"
}
```

**Response (202 Accepted):**
```json
{
  "task_id": "dpt-task-550e8400-e29b",
  "status": "processing",
  "message": "Document queued for inference",
  "estimated_completion_sec": 5
}
```

**Response (200 OK) [Synchronous Mode]:**
*If the document is small enough, the service may return results immediately.*
```json
{
  "task_id": "dpt-task-550e8400-e29b",
  "status": "completed",
  "extracted_data": {
    "employer_name": "Acme Corp",
    "employment_income": "85000.00",
    "ytd_income": "21250.00",
    "tax_year": "2025"
  },
  "confidence_score": 0.98
}
```

**Errors:**
- `400 Bad Request`: Invalid `document_type` or S3 path format.
- `401 Unauthorized`: Invalid or missing bearer token.
- `404 Not Found`: Object does not exist in the specified S3 bucket.
- `422 Unprocessable Entity`: Document is corrupted or not a valid PDF.
- `500 Internal Server Error`: Model inference failure.

---

## GET /api/v1/document-processing/status/{task_id}

Retrieves the status and results of an asynchronous processing task.

**Parameters:**
- `task_id` (path): The UUID returned by the POST endpoint.

**Response (200 OK):**
```json
{
  "task_id": "dpt-task-550e8400-e29b",
  "status": "completed",
  "created_at": "2026-03-02T14:30:00Z",
  "updated_at": "2026-03-02T14:30:05Z",
  "result": {
    "document_type": "NOA",
    "line_15000": "95000.00",
    "line_23600": "88000.00",
    "tax_year": "2024"
  },
  "model_version": "donut-noa-v1.2"
}
```

**Response (202 OK):**
*If processing is still in progress.*
```json
{
  "task_id": "dpt-task-550e8400-e29b",
  "status": "processing",
  "message": "Inference in progress"
}
```

**Errors:**
- `404 Not Found`: Task ID does not exist.
```

### 2. Module README

**File:** `docs/modules/document_processing_transformer.md`

```markdown
# Document Processing Transformer (DPT) Module

## Overview
The DPT module is a specialized microservice designed to convert unstructured borrower documents into structured JSON data. It leverages **Donut** (an OCR-free document understanding transformer) to extract key financial metrics required for the Canadian Mortgage Underwriting System.

## Key Features
- **OCR-Free Processing:** Uses vision-based transformer models (Donut) to understand document layout without intermediate text layers.
- **Fine-Tuned Models:** Hosts specific models for Canadian mortgage documents:
  - `donut-t4506`: Trained on 500+ T4/T4A slips. Extracts employer, income, deductions.
  - `donut-noa`: Trained on 500+ Notices of Assessment. Extracts Line 15000, 23600.
  - `donut-credit`: Trained on 1,000+ Equifax/TransUnion reports.
- **S3 Integration:** Directly pulls objects from secured S3 buckets to minimize data movement.

## Regulatory Compliance
- **PIPEDA:** 
  - SIN and DOB fields are identified by the model but **must be encrypted immediately upon receipt** by the calling service.
  - Raw document text is never logged; only the structured JSON output is stored in the database.
- **FINTRAC:**
  - All extraction attempts are logged with `correlation_id` and `created_at` timestamps for audit trails.
  - No data is deleted; results are immutable once written to the database.

## Usage Example

### Python Client (using httpx)

```python
import httpx

async def process_t4(s3_key: str):
    async with httpx.AsyncClient() as client:
        payload = {
            "s3_bucket": "mortgage-docs-prod",
            "s3_key": s3_key,
            "document_type": "T4",
            "correlation_id": "app-123"
        }
        resp = await client.post(
            "https://api.mortgage.internal/v1/document-processing/extract",
            json=payload,
            headers={"Authorization": "Bearer ..."}
        )
        
        task_data = resp.json()
        if task_data["status"] == "processing":
            # Poll status endpoint
            pass
        else:
            # Handle extracted data
            income = Decimal(task_data["extracted_data"]["employment_income"])
```

## Architecture Notes
- **Async Inference:** The service uses FastAPI's `BackgroundTasks` or a Celery worker (depending on deployment config) to handle the heavy CPU load of the transformer model without blocking the event loop.
- **Model Caching:** Models are loaded into memory on startup to minimize latency during requests.
```

### 3. Configuration Notes

**File:** `.env.example` (Append these entries)

```bash
# Document Processing Transformer (DPT) Service Configuration

# AWS S3 Access for document ingestion
DPT_AWS_REGION=ca-central-1
DPT_S3_BUCKET_NAME=mortgage-docs-prod
DPT_S3_ACCESS_KEY_ID=AKIA...
DPT_S3_SECRET_ACCESS_KEY=...

# HuggingFace / Model Configuration
# If using private models or specific Hub versions
HUGGINGFACE_TOKEN=hf_...
DPT_MODEL_CACHE_DIR=/var/cache/donut_models
DPT_DEVICE=cuda # or 'cpu' for development

# Processing Limits
DPT_MAX_FILE_SIZE_MB=10
DPT_TIMEOUT_SECONDS=30
```