```json
[
  {
    "title": "Document Upload Service Fails on Empty File Input",
    "description": "The document upload service raises a TypeError when an empty file input is provided. The root cause is a lack of validation for empty file streams before attempting to read content.",
    "test_name": "tests/unit/test_document_management.py::test_upload_empty_file",
    "error_type": "TypeError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/document_management/services.py\", line 32, in upload_document\n    content = await file.read()\n  File \"/usr/local/lib/python3.12/site-packages/starlette/datastructures.py\", line 756, in read\n    return b''.join(self._file)\nTypeError: sequence item 0: expected a bytes-like object, NoneType found",
    "error_message": "sequence item 0: expected a bytes-like object, NoneType found",
    "affected_code": [
      "mortgage_underwriting/modules/document_management/services.py",
      "line 32"
    ],
    "suggested_fix": "Add validation to check if file stream is valid and not empty before calling file.read(). Return structured error response for invalid inputs.",
    "severity": "high"
  },
  {
    "title": "Document Metadata Not Persisted Due to Missing Field Mapping",
    "description": "Document metadata such as uploaded_by and source_application are not persisted due to incorrect ORM mapping in the Document model. This causes silent data loss during creation.",
    "test_name": "tests/integration/test_document_management_integration.py::test_document_metadata_persistence",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_document_management_integration.py\", line 88, in test_document_metadata_persistence\n    assert saved_doc.uploaded_by == \"agent_123\"\nAssertionError",
    "error_message": "assert None == 'agent_123'",
    "affected_code": [
      "mortgage_underwriting/modules/document_management/models.py",
      "line 24"
    ],
    "suggested_fix": "Ensure all metadata fields are mapped correctly in the SQLAlchemy model definition. Add explicit column definitions for uploaded_by and source_application.",
    "severity": "high"
  },
  {
    "title": "List Documents Endpoint Allows Unlimited Query Size",
    "description": "The list documents endpoint does not enforce a maximum limit on query size, violating pagination best practices and exposing potential performance risks.",
    "test_name": "tests/unit/test_document_management.py::test_list_documents_no_limit_enforced",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_document_management.py\", line 112, in test_list_documents_no_limit_enforced\n    assert len(response.data['documents']) <= 100\nAssertionError",
    "error_message": "assert 500 <= 100",
    "affected_code": [
      "mortgage_underwriting/modules/document_management/routes.py",
      "line 67"
    ],
    "suggested_fix": "Implement a maximum limit of 100 items per page in the route handler. Clamp user-provided limit parameter to this cap.",
    "severity": "high"
  },
  {
    "title": "Foreign Key Constraint Missing OnDelete Behavior",
    "description": "Foreign key constraints in the Document model do not specify ondelete behavior, which violates regulatory requirements for immutable audit trails and may lead to orphaned records.",
    "test_name": "tests/unit/test_document_management.py::test_foreign_key_ondelete_behavior",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_document_management.py\", line 145, in test_foreign_key_ondelete_behavior\n    assert 'ON DELETE CASCADE' in ddl_sql\nAssertionError",
    "error_message": "Constraint does not include ON DELETE behavior",
    "affected_code": [
      "mortgage_underwriting/modules/document_management/models.py",
      "line 18"
    ],
    "suggested_fix": "Update ForeignKey definitions to include explicit ondelete='CASCADE' or appropriate referential action based on business rules.",
    "severity": "high"
  },
  {
    "title": "Float Used Instead of Decimal for File Size Field",
    "description": "File size field uses float instead of Decimal, violating monetary and precise numeric storage conventions. This could introduce rounding errors in reporting or billing logic.",
    "test_name": "tests/unit/test_document_management.py::test_file_size_precision_loss",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_document_management.py\", line 95, in test_file_size_precision_loss\n    assert isinstance(doc.file_size, Decimal)\nAssertionError",
    "error_message": "Expected Decimal, got float",
    "affected_code": [
      "mortgage_underwriting/modules/document_management/models.py",
      "line 15"
    ],
    "suggested_fix": "Change the file_size field type from Float to Decimal(19, 4) in the Document model to ensure precision compliance.",
    "severity": "high"
  }
]
```