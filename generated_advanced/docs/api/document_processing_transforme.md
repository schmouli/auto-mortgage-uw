Here is the documentation for the Document Processing Transformer (DPT) Service module.

### 1. API Documentation

**File:** `docs/api/document_processing_transformer.md`

```markdown
# Document Processing Transformer (DPT) Service API

This microservice handles the ingestion of mortgage-related documents from S3, performs OCR-free inference using fine-tuned Donut models, and returns structured JSON data for underwriting.

## POST /api/v1/dpt/extract

Extracts structured data from a specific document stored in S3.

**Request:**
```json
{
  "s3_key": "uploads/borrower_abc123/t4_2023.pdf",
  "document_type": "t4506",
  "borrower_id": "uuid-v4-string"
}
```

**Request Fields:**
- `s3_key` (str): The path to the PDF file in the configured S3 bucket.
- `document_type` (str): The model pipeline to use. Supported values: `t4506`, `noa`, `credit`.
- `borrower_id` (str): UUID of the borrower for audit trails (FINTRAC compliance).

**Response (200 OK):**
```json
{
  "extraction_id": "uuid-v4-string",
  "document_type": "t4506",
  "data": {
    "employer_name": "Acme Corp",
    "employment_income": "85000.00",
    "income_tax_deducted": "15000.00",
    "year_to_date": "42500.00",
    "tax_year": "2023"
  },
  "confidence_score": 0.98,
  "processing_time_ms": 1250,
  "created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- `400 Bad Request`: Invalid `document_type` or malformed S3 key.
- `404 Not Found`: File not found in S3 bucket.
- `422 Unprocessable Entity`: Donut model failed to generate valid JSON or confidence score below threshold.
- `503 Service Unavailable`: Model is loading or inference server is down.

---

## GET /api/v1/dpt/extraction/{extraction_id}

Retrieves a previous extraction result by ID.

**Response (200 OK):**
```json
{
  "id": "uuid-v4-string",
  "s3_key": "uploads/borrower_abc123/t4_2023.pdf",
  "document_type": "t4506",
  "data": { ... },
  "created_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- `404 Not Found`: Extraction ID does not exist.

---

## POST /api/v1/dpt/validate

Validates extracted data against underwriting rules (e.g., ensuring tax years match).

**Request:**
```json
{
  "extraction_id": "uuid-v4-string",
  "application_tax_year": 2023
}
```

**Response (200 OK):**
```json
{
  "valid": true,
  "warnings": [],
  "errors": []
}
```
```

### 2. Module README

**File:** `docs/modules/dpt_service.md`

```markdown
# Document Processing Transformer (DPT) Service

## Overview
The DPT Service is responsible for converting unstructured borrower documents (PDFs) into structured JSON data suitable for the Canadian Mortgage Underwriting System. It utilizes the `Donut` (Document Understanding Transformer) architecture, which is an OCR-free approach, reducing errors common in traditional OCR pipelines.

## Key Features
- **S3 Integration**: Ingests documents directly from a secure AWS S3 bucket.
- **Fine-tuned Models**: Uses specialized models for specific Canadian mortgage documents:
  - **donut-t4506**: Trained on 500+ T4/T4A slips to extract employment income, deductions, and employer details.
  - **donut-noa**: Trained on 500+ Notices of Assessment (NOA) to extract Line 15000 (Gross Income), Line 23600 (Net Income), and Tax Year.
  - **donut-credit**: Trained on 1,000+ Equifax/TransUnion reports to extract credit scores and trade lines.
- **FINTRAC Compliance**: All extraction results are stored immutably with timestamps and borrower references.

## Architecture
1. **Ingestion**: The `routes.py` endpoint receives a request with an S3 key.
2. **Preprocessing**: The `services.py` layer downloads the PDF, converts it to an image tensor (required by Donut).
3. **Inference**: The appropriate model is loaded (cached) and runs inference to generate a JSON string token by token.
4. **Post-processing**: The generated string is parsed into a Pydantic schema. If parsing fails, a `422` error is returned.

## Usage Example

### Python Client
```python
import httpx

async def extract_t4_data(s3_key: str, borrower_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://dpt-service/api/v1/dpt/extract",
            json={
                "s3_key": s3_key,
                "document_type": "t4506",
                "borrower_id": borrower_id
            }
        )
        response.raise_for_status()
        return response.json()["data"]
```

### Handling Financial Data
All monetary values returned by the DPT service are strings formatted as Decimals (e.g., `"85000.00"`). The consuming service must cast these to `Decimal` before performing any GDS/TDS calculations to ensure compliance with project rules.

## Error Handling
The service distinguishes between:
- **System Errors**: S3 timeouts, Model load failures (HTTP 5xx).
- **Validation Errors**: The document is of the wrong type, or the model failed to extract data (HTTP 422).
```

### 3. Configuration Notes

**File:** `.env.example` (Updates)

```bash
# Document Processing Transformer (DPT) Configuration

# S3 Storage for Ingestion
AWS_S3_BUCKET_NAME=mortgage-docs-prod
AWS_S3_REGION=ca-central-1
DPT_S3_INPUT_PREFIX=uploads/

# Model Artifacts
# Local path or S3 path where the .pth/.safetensors files are stored
DPT_MODEL_BASE_PATH=/models/donut_fine_tunes
DPT_DEVICE=cuda # or 'cpu' for development

# Inference Parameters
DPT_MAX_LENGTH=2048
DPT_BATCH_SIZE=1
DPT_CONFIDENCE_THRESHOLD=0.85

# Security
# Encryption key for masking specific extracted PII before logging (if applicable)
DPT_LOG_ENCRYPTION_KEY=
```

### 4. Changelog Update

**File:** `CHANGELOG.md`

```markdown
## [2026-03-02]
### Added
- Document Processing Transformer (DPT) Service: New microservice for PDF ingestion and extraction.
- Endpoints: POST /api/v1/dpt/extract, GET /api/v1/dpt/extraction/{id}, POST /api/v1/dpt/validate.
- Integration with Donut models: donut-t4506, donut-noa, and donut-credit.
- Support for OCR-free inference pipeline.

### Changed
- Updated common/security.py to support encrypted logging for extracted PII fields.

### Fixed
- N/A
```