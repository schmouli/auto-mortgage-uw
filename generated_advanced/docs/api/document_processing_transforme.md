```markdown
# Document Processing Transformer (DPT) Service API

## Overview

The Document Processing Transformer (DPT) Service is a specialized microservice designed to ingest borrower documents (PDFs) stored in S3 and perform structured data extraction using the Donut vision-language model (OCR-free).

This service is fine-tuned specifically for the Canadian mortgage underwriting context, supporting the following document types:
- **T4/T4A Slips (`donut-t4506`)**: Extracts employment income, deductions, year-to-date (YTD) figures, and employer details.
- **Notices of Assessment (`donut-noa`)**: Extracts Line 15000 (Total Income), Line 23600 (Net Income), and the tax year.
- **Credit Reports (`donut-credit`)**: Extracts data from Equifax/TransUnion reports (score, trade lines, liabilities).

### Regulatory & Security Compliance
- **PIPEDA**: Raw Personally Identifiable Information (PII) such as Social Insurance Numbers (SIN) and Dates of Birth (DOB) are **never** returned in API responses or logged. Sensitive fields are either masked (e.g., `***-***-123`) or referenced via secure tokens if required for downstream matching.
- **Data Minimization**: Only fields strictly required for underwriting calculations are extracted and returned.
- **Auditability**: All extraction requests are logged with a `correlation_id` but document content is never logged.

---

## Configuration

To operate the DPT service, the following environment variables must be configured in `.env`:

```bash
# AWS S3 Configuration
S3_BUCKET_NAME=mortgage-docs-bucket
AWS_REGION=ca-central-0
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# Model Configuration
DPT_MODEL_CACHE_DIR=/app/models
INFERENCE_DEVICE=cuda # or 'cpu'
MAX_FILE_SIZE_MB=10

# Security
ENCRYPTION_KEY_ID=alias/p mortgage-key
```

---

## API Endpoints

### POST /api/v1/dpt/process

Triggers the Donut inference engine to extract structured data from a specified document in S3.

**Request:**
```json
{
  "s3_key": "borrowers/123456/documents/t4_2023.pdf",
  "document_type": "T4",
  "correlation_id": "req_8f9a2b3c"
}
```

**Request Parameters:**
- `s3_key` (string, required): The path to the file within the configured S3 bucket.
- `document_type` (enum, required): The type of document to process. Valid values: `T4`, `NOA`, `CREDIT`.
- `correlation_id` (string, optional): Unique ID for tracing across logs.

**Response (200 OK):**
```json
{
  "id": "ext_99887766",
  "document_type": "T4",
  "status": "success",
  "extracted_data": {
    "employer_name": "Acme Corp",
    "year": "2023",
    "gross_income": "85000.00",
    "income_tax_deducted": "15000.00",
    "cpp_deducted": "3200.00",
    "ei_deducted": "800.00",
    "sin_masked": "***-***-123"
  },
  "confidence_score": 0.98,
  "processed_at": "2026-03-02T14:30:00Z"
}
```

**Errors:**
- `400 Bad Request`: Invalid `document_type` or missing `s3_key`.
- `404 Not Found`: File does not exist in the specified S3 bucket.
- `413 Payload Too Large`: File size exceeds `MAX_FILE_SIZE_MB`.
- `422 Unprocessable Entity`: Document is corrupted, unreadable, or format is unsupported.
- `500 Internal Server Error`: Model inference failure or S3 connectivity issue.

---

### POST /api/v1/dpt/process/noa

Specialized endpoint for Notices of Assessment to ensure precise capture of tax lines required for income verification.

**Request:**
```json
{
  "s3_key": "borrowers/123456/documents/noa_2023.pdf",
  "correlation_id": "req_1a2b3c4d"
}
```

**Response (200 OK):**
```json
{
  "id": "ext_11223344",
  "document_type": "NOA",
  "status": "success",
  "extracted_data": {
    "tax_year": "2023",
    "line_15000_total_income": "92000.00",
    "line_23600_net_income": "74000.00",
    "tax_payable": "12500.00"
  },
  "confidence_score": 0.95,
  "processed_at": "2026-03-02T14:31:00Z"
}
```

**Errors:**
- `422 Unprocessable Entity`: Required tax lines (15000, 23600) could not be found or read with sufficient confidence.

---

### POST /api/v1/dpt/process/credit

Processes Equifax or TransUnion credit reports to summarize liabilities and scores.

**Request:**
```json
{
  "s3_key": "borrowers/123456/documents/credit_report.pdf",
  "correlation_id": "req_9z8y7x6w"
}
```

**Response (200 OK):**
```json
{
  "id": "ext_55443322",
  "document_type": "CREDIT",
  "status": "success",
  "extracted_data": {
    "bureau": "Equifax",
    "credit_score": 720,
    "total_monthly_debt": "1850.00",
    "trade_lines": [
      {
        "creditor": "RBC",
        "balance": "5000.00",
        "limit": "10000.00",
        "payment": "150.00"
      }
    ]
  },
  "confidence_score": 0.91,
  "processed_at": "2026-03-02T14:32:00Z"
}
```

**Errors:**
- `401 Unauthorized`: Invalid permissions to access credit report data.
- `422 Unprocessable Entity`: Unable to parse credit summary tables.

---

## Changelog

## [2026-03-02]
### Added
- Document Processing Transformer (DPT) Service: Initial API endpoints for T4, NOA, and Credit report ingestion.
- Integration with Donut (OCR-free) models for mortgage document extraction.
- Support for S3-based document retrieval.
- PII masking logic for SIN and DOB fields in API responses.
```