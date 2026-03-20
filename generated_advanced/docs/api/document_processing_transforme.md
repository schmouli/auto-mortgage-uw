Here is the documentation for the Document Processing Transformer (DPT) Service module.

### 1. API Documentation

**File:** `docs/api/dpt_service.md`

```markdown
# Document Processing Transformer (DPT) Service API

## POST /api/v1/dpt/process

Ingests a borrower document from S3, runs the specified Donut inference model, and returns structured JSON data extraction.

**Request:**
```json
{
  "s3_key": "uploads/application_123/t4_slips/john_doe_t4.pdf",
  "document_type": "t4506",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Parameters:**
- `s3_key` (string, required): The path to the document in the configured S3 bucket.
- `document_type` (string, required): The model identifier to use for inference. Allowed values: `t4506`, `noa`, `credit`.
- `correlation_id` (string, optional): Request ID for tracing.

**Response (200 OK):**
```json
{
  "id": "ext_8823910",
  "document_type": "t4506",
  "status": "success",
  "extracted_data": {
    "employer_name": "Acme Corp",
    "employment_income": "85000.00",
    "ytd_income": "21250.00",
    "deductions": "4500.00"
  },
  "confidence_score": 0.98,
  "processed_at": "2026-03-02T14:30:00Z"
}
```

**Response Examples for other types:**

*T4/T4A (t4506):*
```json
{
  "extracted_data": {
    "employer": "Acme Corp",
    "gross_income": "85000.00",
    "ytd": "21250.00",
    "deductions": "4500.00"
  }
}
```

*NOA (noa):*
```json
{
  "extracted_data": {
    "tax_year": 2023,
    "line_15000": "92000.00",
    "line_23600": "88000.00"
  }
}
```

*Credit Report (credit):*
```json
{
  "extracted_data": {
    "beacon_score": 720,
    "total_debt": "15000.00",
    "missed_payments": 0
  }
}
```

**Errors:**
- `400 Bad Request`: Invalid `document_type` or empty S3 key.
- `404 Not Found`: Document not found in S3 bucket.
- `422 Unprocessable Entity`: Validation error on request payload.
- `500 Internal Server Error`: Model inference failure or S3 connection error.

---
```

### 2. Module README

**File:** `docs/modules/dpt_service.md`

```markdown
# Document Processing Transformer (DPT) Service

## Overview
The DPT Service is responsible for converting unstructured borrower documents (PDFs) into structured JSON data suitable for the mortgage underwriting engine. It utilizes **Donut** (Document Understanding Transformer), an OCR-free approach to visual document understanding.

## Key Functions
- **Ingestion**: Retrieves documents securely from a pre-configured Amazon S3 bucket.
- **Inference**: Routes documents to specific fine-tuned Donut models based on document type.
- **Extraction**: Returns key financial data points (e.g., Income, Debt, Tax Years) in JSON format.

## Supported Document Types
The service currently supports three fine-tuned model variants:

| Model Key | Document Type | Description | Extracted Fields |
| :--- | :--- | :--- | :--- |
| `t4506` | T4 / T4A Slips | Employment income verification | Employer Name, Gross Income, YTD, Deductions |
| `noa` | Notice of Assessment | Tax return summary | Tax Year, Line 15000 (Total Income), Line 23600 (Net Income) |
| `credit` | Credit Report | Bureau data (Equifax/TransUnion) | Beacon Score, Total Debt, Payment History |

## Regulatory Compliance
- **PIPEDA**: Raw document text is never logged. Only structured JSON outputs are persisted. Sensitive identifiers (SIN) found in extractions are handled by the downstream encryption service.
- **FINTRAC**: All extraction results are treated as financial records and include immutable audit trails (`created_at`, `created_by`).

## Usage Example

```python
import httpx

async def process_t4():
    async with httpx.AsyncClient() as client:
        payload = {
            "s3_key": "uploads/app_789/t4_2023.pdf",
            "document_type": "t4506"
        }
        response = await client.post(
            "http://dpt-service/api/v1/dpt/process",
            json=payload
        )
        return response.json()
```

## Dependencies
- `torch`: Donut inference backend.
- `boto3`: S3 integration.
- `transformers`: HuggingFace model loading.
```

### 3. Configuration Notes

**File:** `.env.example`

```bash
# Document Processing Transformer (DPT) Service Configuration

# S3 Storage
DPT_S3_BUCKET_NAME=mortgage-docs-ingest-prod
DPT_AWS_REGION=ca-central-1

# Model Paths (Local or S3 URI)
# T4/T4A Model (donut-t4506)
DPT_MODEL_PATH_T4506=/models/donut-t4506

# NOA Model (donut-noa)
DPT_MODEL_PATH_NOA=/models/donut-noa

# Credit Report Model (donut-credit)
DPT_MODEL_PATH_CREDIT=/models/donut-credit

# Inference Settings
DPT_DEVICE=cuda # or 'cpu'
DPT_MAX_BATCH_SIZE=4
```

### 4. CHANGELOG Update

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Document Processing Transformer (DPT) Service: New module for OCR-free document ingestion.
- POST /api/v1/dpt/process: Endpoint to trigger Donut inference on S3 PDFs.
- Support for T4/T4A, NOA, and Credit Report extraction models.
- Configuration for S3 bucket integration and model path routing.

### Changed
- Updated common/security.py to support S3 signature verification for incoming webhooks (future proofing).

### Fixed
- N/A
```