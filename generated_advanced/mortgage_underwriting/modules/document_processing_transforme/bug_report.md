```json
[
  {
    "title": "Document parsing fails on malformed upload metadata",
    "description": "Service raises KeyError when processing document uploads missing optional 'upload_metadata' field. Caused by direct dictionary access without .get() fallback.",
    "test_name": "tests/unit/test_document_processing_transformer.py::test_parse_upload_missing_metadata",
    "error_type": "KeyError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_document_processing_transformer.py\", line 78, in test_parse_upload_missing_metadata\n    result = await service.parse_upload(raw_doc)\n  File \"mortgage_underwriting/modules/document_processing_transformer/services.py\", line 32, in parse_upload\n    metadata = raw_doc['upload_metadata']\nKeyError: 'upload_metadata'",
    "error_message": "'upload_metadata'",
    "affected_code": [
      "mortgage_underwriting/modules/document_processing_transformer/services.py",
      "line 32"
    ],
    "suggested_fix": "Replace direct key access with .get() and default value: metadata = raw_doc.get('upload_metadata', {})",
    "severity": "high"
  },
  {
    "title": "PII leakage in exception logging during document validation",
    "description": "Validation error includes borrower_sin in exception message which gets logged. Violates PIPEDA encryption/logging requirements.",
    "test_name": "tests/unit/test_document_processing_transformer.py::test_validate_borrower_pii_logging",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_document_processing_transformer.py\", line 112, in test_validate_borrower_pii_logging\n    await service.validate_borrower(bad_data)\n  File \"mortgage_underwriting/modules/document_processing_transformer/services.py\", line 67, in validate_borrower\n    raise ValueError(f\"Invalid SIN {borrower.sin} provided\")\nValueError: Invalid SIN 123456789 provided",
    "error_message": "Invalid SIN 123456789 provided",
    "affected_code": [
      "mortgage_underwriting/modules/document_processing_transformer/services.py",
      "line 67"
    ],
    "suggested_fix": "Remove PII from error messages; log hash or generic identifier instead: e.g., f\"Invalid SIN format for borrower ID {borrower.id}\"",
    "severity": "high"
  },
  {
    "title": "Audit trail missing created_by field during bulk ingestion",
    "description": "Documents processed via bulk_ingest_documents do not populate created_by audit field. FINTRAC requires all financial records to have immutable creator tracking.",
    "test_name": "tests/integration/test_document_processing_transformer_integration.py::test_bulk_ingestion_audit_fields",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/integration/test_document_processing_transformer_integration.py\", line 95, in test_bulk_ingestion_audit_fields\n    assert all(doc.created_by is not None for doc in saved_docs)\nAssertionError",
    "error_message": "assert False",
    "affected_code": [
      "mortgage_underwriting/modules/document_processing_transformer/services.py",
      "line 104"
    ],
    "suggested_fix": "Pass authenticated user context into bulk_ingest_documents method and assign to created_by field during model instantiation",
    "severity": "high"
  },
  {
    "title": "Float used for monetary value in extracted_income_summary",
    "description": "Income summary extraction returns float instead of Decimal for monetary fields. Violates monetary precision policy requiring Decimal(19,4).",
    "test_name": "tests/unit/test_document_processing_transformer.py::test_extract_income_summary_precision",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_document_processing_transformer.py\", line 145, in test_extract_income_summary_precision\n    assert isinstance(result.total_annual_income, Decimal)\nAssertionError",
    "error_message": "assert isinstance(120000.0, Decimal) is False",
    "affected_code": [
      "mortgage_underwriting/modules/document_processing_transformer/services.py",
      "line 178"
    ],
    "suggested_fix": "Cast monetary values to Decimal using Decimal(str(value)) to prevent precision loss from float conversion",
    "severity": "high"
  },
  {
    "title": "Missing updated_at field in DocumentUpload ORM model",
    "description": "DocumentUpload model lacks updated_at column required by audit standards. All models must track modification timestamps.",
    "test_name": "tests/unit/test_document_processing_transformer.py::test_model_updated_at_field_exists",
    "error_type": "AttributeError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_document_processing_transformer.py\", line 52, in test_model_updated_at_field_exists\n    getattr(DocumentUpload, 'updated_at')\nAttributeError: type object 'DocumentUpload' has no attribute 'updated_at'",
    "error_message": "type object 'DocumentUpload' has no attribute 'updated_at'",
    "affected_code": [
      "mortgage_underwriting/modules/document_processing_transformer/models.py",
      "line 28"
    ],
    "suggested_fix": "Add updated_at = Column(DateTime(timezone=True), onupdate=func.now()) to DocumentUpload model definition",
    "severity": "high"
  }
]
```