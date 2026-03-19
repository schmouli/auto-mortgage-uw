```json
[
  {
    "title": "Document Upload Service Fails on Empty Filename",
    "description": "The document upload service raises a TypeError when provided with an empty string for filename. This violates input validation expectations.",
    "test_name": "tests/unit/test_document_management.py::test_upload_empty_filename_raises_error",
    "error_type": "TypeError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_document_management.py\", line 32, in test_upload_empty_filename_raises_error\n    await document_service.upload_document(user_id=1, filename='', content=b'')\n  File \"mortgage_underwriting/modules/document_management/services.py\", line 47, in upload_document\n    if not filename.strip():\nTypeError: a bytes-like object is required, not 'str'",
    "error_message": "a bytes-like object is required, not 'str'",
    "affected_code": [
      "mortgage_underwriting/modules/document_management/services.py",
      "line 47"
    ],
    "suggested_fix": "Ensure that the filename parameter is validated as a string before calling .strip(). Add explicit type check or convert input appropriately.",
    "severity": "high"
  },
  {
    "title": "Audit Trail Not Created for Document Deletion",
    "description": "Documents are deleted without creating an immutable audit trail entry, violating FINTRAC compliance regarding record retention and modification tracking.",
    "test_name": "tests/integration/test_document_management_integration.py::test_delete_document_creates_audit_entry",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/integration/test_document_management_integration.py\", line 88, in test_delete_document_creates_audit_entry\n    assert audit_entry is not None\nAssertionError",
    "error_message": "Audit entry was expected but not found after deletion.",
    "affected_code": [
      "mortgage_underwriting/modules/document_management/models.py",
      "line 62"
    ],
    "suggested_fix": "Implement soft-delete pattern with status field instead of hard deletes. Ensure every delete action creates a corresponding audit log in the `document_audits` table.",
    "severity": "high"
  },
  {
    "title": "PII Exposure in Logs During Document Processing",
    "description": "SIN values were observed in logs during document processing due to improper sanitization in exception handling block.",
    "test_name": "tests/unit/test_document_management.py::test_sin_logging_exposure",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_document_management.py\", line 115, in test_sin_logging_exposure\n    assert 'SIN' not in caplog.text\nAssertionError",
    "error_message": "PII (SIN) exposed in application logs during error handling.",
    "affected_code": [
      "mortgage_underwriting/modules/document_management/services.py",
      "line 92"
    ],
    "suggested_fix": "Sanitize all PII fields using common/security.py utilities before including them in log statements. Replace sensitive data with placeholders like '<REDACTED>'.",
    "severity": "high"
  },
  {
    "title": "Missing updated_at Field in Document Model",
    "description": "Document model does not include updated_at column which is mandatory per regulatory audit requirements.",
    "test_name": "tests/unit/test_document_management.py::test_model_includes_updated_at_field",
    "error_type": "AttributeError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_document_management.py\", line 55, in test_model_includes_updated_at_field\n    getattr(Document, 'updated_at')\nAttributeError: type object 'Document' has no attribute 'updated_at'",
    "error_message": "type object 'Document' has no attribute 'updated_at'",
    "affected_code": [
      "mortgage_underwriting/modules/document_management/models.py",
      "line 20"
    ],
    "suggested_fix": "Add updated_at field to Document model with server_default=func.now() and onupdate=func.now(). Ensure migration script reflects this addition.",
    "severity": "high"
  }
]
```