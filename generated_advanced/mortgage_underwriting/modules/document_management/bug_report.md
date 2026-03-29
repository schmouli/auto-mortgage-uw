```json
[
  {
    "title": "Document upload fails with invalid MIME type validation",
    "description": "The document upload service raises a ValidationError when uploading a valid PDF file due to incorrect MIME type detection logic.",
    "test_name": "tests/unit/test_document_management.py::test_upload_valid_pdf",
    "error_type": "ValidationError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/document_management/services.py\", line 67, in validate_document\n    if mime_type not in ALLOWED_MIME_TYPES:\nTypeError: argument of type 'NoneType' is not iterable\n\nDuring handling of the above exception, another exception occurred:\n\nTraceback (most recent call last):\n  File \"/app/tests/unit/test_document_management.py\", line 42, in test_upload_valid_pdf\n    result = await DocumentService.upload_document(file)\n  File \"/app/mortgage_underwriting/modules/document_management/services.py\", line 102, in upload_document\n    validated_doc = self.validate_document(file)\n  File \"/app/mortgage_underwriting/modules/document_management/services.py\", line 70, in validate_document\n    raise ValidationError(\"Invalid MIME type\")\npydantic_core._pydantic_core.ValidationError: 1 validation error for DocumentUpload\n",
    "error_message": "Invalid MIME type",
    "affected_code": [
      "mortgage_underwriting/modules/document_management/services.py",
      "line 67"
    ],
    "suggested_fix": "Ensure MIME type detection returns a string or handle None explicitly before checking membership in ALLOWED_MIME_TYPES.",
    "severity": "high"
  },
  {
    "title": "Audit log creation fails during document deletion",
    "description": "Attempting to delete a document results in IntegrityError because audit_log_id references a non-existent entry in audit_logs table.",
    "test_name": "tests/integration/test_document_integration.py::test_delete_document_creates_audit_entry",
    "error_type": "IntegrityError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/document_management/models.py\", line 89, in delete_document\n    db.add(audit_entry)\n    db.commit()\nsqlalchemy.exc.IntegrityError: (psycopg2.errors.ForeignKeyViolation) insert or update on table \"documents\" violates foreign key constraint \"fk_documents_audit_log\"\nDETAIL:  Key (audit_log_id)=(999) is not present in table \"audit_logs\".\n",
    "error_message": "(psycopg2.errors.ForeignKeyViolation) insert or update on table \"documents\" violates foreign key constraint \"fk_documents_audit_log\"",
    "affected_code": [
      "mortgage_underwriting/modules/document_management/models.py",
      "line 85"
    ],
    "suggested_fix": "Ensure audit log entry is inserted and committed before referencing its ID in documents table; consider using transaction.atomic() to ensure consistency.",
    "severity": "high"
  },
  {
    "title": "List endpoint missing pagination support",
    "description": "Calling GET /documents without limit parameter fetches all rows causing timeout for large datasets.",
    "test_name": "tests/integration/test_document_routes.py::test_list_documents_no_pagination",
    "error_type": "TimeoutError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_document_routes.py\", line 65, in test_list_documents_no_pagination\n    response = client.get('/api/v1/documents')\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_client.py\", line 1023, in get\n    return self.request(\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_client.py\", line 837, in request\n    return self.send(request, auth=auth, follow_redirects=follow_redirects)\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_client.py\", line 926, in send\n    response = self._send_handling_auth(\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_client.py\", line 954, in _send_handling_auth\n    response = self._send_handling_redirects(\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_client.py\", line 991, in _send_handling_redirects\n    response = self._send_single_request(request)\n  File \"/usr/local/lib/python3.12/site-packages/httpx/_client.py\", line 1027, in _send_single_request\n    response = transport.handle_request(request)\nhttpx.ReadTimeout\n",
    "error_message": "ReadTimeout while fetching documents list",
    "affected_code": [
      "mortgage_underwriting/modules/document_management/routes.py",
      "line 55"
    ],
    "suggested_fix": "Implement default pagination parameters (skip=0, limit=20) and enforce maximum limit of 100 per FINTRAC compliance.",
    "severity": "medium"
  }
]
```