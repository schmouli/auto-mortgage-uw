```json
[
  {
    "title": "Document parsing fails on null borrower SIN field",
    "description": "The service raises a TypeError when attempting to process documents where the borrower's SIN is None. This violates PIPEDA compliance which mandates encryption/hashing of SIN fields, but also requires graceful degradation or clear error messaging when fields are missing.",
    "test_name": "tests/unit/test_dpt_service.py::test_parse_document_with_missing_sin",
    "error_type": "TypeError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/dpt/services.py\", line 78, in parse_document\n    encrypted_sin = encrypt_pii(borrower.sin)\n  File \"/app/mortgage_underwriting/common/security.py\", line 32, in encrypt_pii\n    if not data:\n      ^^^^^^^^\nTypeError: 'NoneType' object is not iterable",
    "error_message": "'NoneType' object is not iterable",
    "affected_code": [
      "mortgage_underwriting/modules/dpt/services.py",
      "line 78"
    ],
    "suggested_fix": "Add pre-validation check for None values in borrower data before calling encrypt_pii(). Raise InputValidationError with descriptive message.",
    "severity": "high"
  },
  {
    "title": "Audit log entry missing for successful document transformation",
    "description": "FINTRAC compliance requires immutable audit trails for all financial transactions. The DPT service does not persist audit metadata after processing a valid document, leading to gaps in traceability.",
    "test_name": "tests/integration/test_dpt_integration.py::test_successful_audit_log_creation",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_dpt_integration.py\", line 112, in test_successful_audit_log_creation\n    assert audit_entry.created_at is not None\nAssertionError",
    "error_message": "assert None",
    "affected_code": [
      "mortgage_underwriting/modules/dpt/services.py",
      "line 105"
    ],
    "suggested_fix": "Ensure that upon successful document processing, an AuditLog entry is committed using common.database.AuditLogger.log_event(). Include correlation_id, timestamp, action='document_processed'.",
    "severity": "high"
  },
  {
    "title": "Large PDF upload causes timeout during extraction",
    "description": "Processing large (>50MB) PDF documents leads to HTTP timeout due to synchronous blocking I/O in pdfminer usage. Should offload heavy operations or enforce size limits.",
    "test_name": "tests/integration/test_dpt_integration.py::test_large_pdf_upload_timeout",
    "error_type": "TimeoutError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/dpt/services.py\", line 142, in extract_text_from_pdf\n    interpreter.process_page(page)\n  File \"/usr/local/lib/python3.12/site-packages/pdfminer/pdfinterp.py\", line 897, in process_page\n    self.render_contents(page.resources, page.contents, ctm=ctm)\n  ... [truncated]\nTimeoutError: Request timed out after 30 seconds",
    "error_message": "Request timed out after 30 seconds",
    "affected_code": [
      "mortgage_underwriting/modules/dpt/services.py",
      "line 142"
    ],
    "suggested_fix": "Offload PDF parsing to background worker via Celery/RQ, or implement streaming parser with early exit on content limit. Alternatively, set strict file size cap (<10MB) and reject larger uploads upfront.",
    "severity": "medium"
  },
  {
    "title": "Incorrect CMHC insurance flagging for edge-case LTV ratios",
    "description": "Documents with calculated LTV exactly at 80% incorrectly trigger insurance requirement due to floating point comparison instead of precise Decimal-based thresholds.",
    "test_name": "tests/unit/test_dpt_service.py::test_cmhc_insurance_flag_exact_80_percent",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_dpt_service.py\", line 65, in test_cmhc_insurance_flag_exact_80_percent\n    assert result.insurance_required == False\nAssertionError",
    "error_message": "assert True == False",
    "affected_code": [
      "mortgage_underwriting/modules/dpt/models.py",
      "line 52"
    ],
    "suggested_fix": "Replace direct float comparisons with Decimal-aware threshold checks using Decimal('0.80') and appropriate rounding strategy per OSFI guidelines.",
    "severity": "high"
  },
  {
    "title": "Missing index on document status column causes slow queries",
    "description": "Querying processed vs unprocessed documents takes over 2 seconds due to lack of database indexing on the status field used in filtering.",
    "test_name": "tests/unit/test_dpt_performance.py::test_query_processing_status_speed",
    "error_type": "PerformanceWarning",
    "stack_trace": "N/A (performance observation)",
    "error_message": "Query took 2.34s, expected <0.5s",
    "affected_code": [
      "mortgage_underwriting/modules/dpt/models.py",
      "line 28"
    ],
    "suggested_fix": "Add database index on the status column in Document model: Index('ix_document_status', 'status')",
    "severity": "medium"
  }
]
```