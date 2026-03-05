Here is the documentation for the Document Processing Transformer (DPT) Service, split into the requested components.

### 1. API Documentation
**File Path:** `docs/api/document_processing_transformer.md`

```markdown
# Document Processing Transformer (DPT) API

This module handles the ingestion of mortgage-related documents from S3, performs OCR-free extraction using fine-tuned Donut models, and returns structured JSON data compliant with OSFI B-20 and PIPEDA requirements.

---

## POST /api/v1/document-processing/extract

Initiates an asynchronous document extraction task.

**Request:**
```json
{
  "document_type": "t4506",
  "s3_bucket": "mortgage-ingestion-zone",
  "s3_key": "applications/app_123/borrower_1/t4_2023.pdf"
}
```

**Valid `document_type` values:**
- `t4506`: T4/T4A slips (Employment income, deductions, YTD, employer)
- `noa`: Notice of Assessment (Line 15000, Line 23600, tax year)
- `credit`: Equifax/TransUnion reports

**Response (202 Accepted):**
```json
{
  "task_id": "f7b3a1d4-8c2e-4f9a-b1d6-9e5f0a2c3d4e",
  "status": "processing",
  "message": "Document queued for extraction"
}
```

**Errors:**
- `400 Bad Request`: Invalid `document_type` or missing S3 parameters.
- `401 Unauthorized`: Invalid or missing authentication token.
- `404 Not Found`: Specified S3 object does not exist or access is denied.
- `422 Unprocessable Entity`: Malformed request body.

---

## GET /api/v1/document-processing/tasks/{task_id}

Retrieves the status and results of a processing task.

**Response (200 OK) - Processing:**
```json
{
  "task_id": "f7b3a1d4-8c2e-4f9a-b1d6-9e5f0a2c3d4e",
  "status": "processing",
  "created_at": "2026-03-02T14:30:00Z"
}
```

**Response (200 OK) - Completed (Example: T4 Slip):**
```json
{
  "task_id": "f7b3a1d4-8c2e-4f9a-b1d6-9e5f0a2c3d4e",
  "status": "completed",
  "document_type": "t4506",
  "model_version": "donut-t4506-v1",
  "extracted_data": {
    "employer_name": "Acme Corp",
    "gross_income": "85000.00",
    "income_tax_deducted": "15000.00",
    "year": "2023"
  },
  "confidence_score": 0.98,
  "completed_at": "2026-03-02T14:30:05Z"
}
```

**Response (200 OK) - Completed (Example: NOA):**
```json
{
  "task_id": "...",
  "status": "completed",
  "document_type": "noa",
  "extracted_data": {
    "line_15000": "92000.00",
    "line_23600": "88000.00",
    "tax_year": "2023"
  }
}
```

**Errors:**
- `404 Not Found`: Task ID does not exist.
- `500 Internal Server Error`: Inference model failure or internal system error.

**Security Notes:**
- Sensitive PII (e.g., SIN) extracted from documents is **hashed** or **masked** in the API response.
- Raw document images are never returned by the API.
```

### 2. Module README
**File Path:** `docs/modules/document_processing_transformer.md`

```markdown
# Document Processing Transformer (DPT) Service

## Overview
The DPT Service is a specialized microservice within the Canadian Mortgage Underwriting System designed to automate the ingestion of financial documents. It replaces traditional OCR with a state-of-the-art Donut (Document Understanding Transformer) approach, providing higher accuracy for structured mortgage forms.

## Key Functions
- **Ingestion**: Retrieves PDF documents securely from Amazon S3 buckets.
- **Inference**: Runs one of three fine-tuned Donut models (176M params) depending on the document type:
  - `donut-t4506`: Trained on 500+ T4/T4A slips. Extracts employment income, CPP/EI deductions, YTD figures, and employer details.
  - `donut-noa`: Trained on 500+ Notices of Assessment. Specifically targets Line 15000 (Total Income) and Line 23600 (Net Income) for GDS/TDS calculations.
  - `donut-credit`: Trained on 1,000+ Equifax/TransUnion reports to parse credit scores and liabilities.
- **Sanitization**: Automatically detects and hashes PII (SIN, DOB) before returning data to ensure PIPEDA compliance.

## Usage Example

```python
import httpx

async def process_t4():
    async with httpx.AsyncClient() as client:
        # 1. Submit document
        response = await client.post(
            "https://api.mortgage-system.com/api/v1/document-processing/extract",
            json={
                "document_type": "t4506",
                "s3_bucket": "secure-uploads",
                "s3_key": "loan_456/t4.pdf"
            },
            headers={"Authorization": "Bearer ..."}
        )
        task_id = response.json()["task_id"]

        # 2. Poll for result
        result = await client.get(f"/api/v1/document-processing/tasks/{task_id}")
        if result.json()["status"] == "completed":
            income = result.json()["extracted_data"]["gross_income"]
            print(f"Verified Income: {income}")
```

## Architecture Notes
- **Async Processing**: Document inference is CPU-intensive. This module utilizes background workers (via FastAPI `BackgroundTasks` or Celery) to prevent blocking the main API thread.
- **Model Storage**: Models are loaded at startup and kept in memory to minimize inference latency.
- **Audit Logging**: All extraction attempts are logged with `correlation_id` but never log the extracted financial data or PII.
```

### 3. Configuration Notes
**File Path:** `.env.example` (Append the following)

```bash
# === Document Processing Transformer (DPT) Service ===

# S3 Configuration for Document Ingestion
DPT_AWS_REGION=ca-central-1
DPT_S3_INGESTION_BUCKET=mortgage-docs-ingestion
DPT_S3_ACCESS_KEY_ID=
DPT_S3_SECRET_ACCESS_KEY=

# Model Configuration
# Path or HuggingFace Hub identifier for the fine-tuned models
DPT_MODEL_T4506=naver-clova-ix/donut-base-finetuned-t4506
DPT_MODEL_NOA=naver-clova-ix/donut-base-finetuned-noa
DPT_MODEL_CREDIT=naver-clova-ix/donut-base-finetuned-credit

# Inference Settings
DPT_DEVICE=cuda  # or 'cpu'
DPT_MAX_LENGTH=2048

# Security
# Salt for hashing SINs/PII found in documents before storage/response
DPT_PII_SALT=
```