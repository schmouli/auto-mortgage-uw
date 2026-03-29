```json
[
  {
    "title": "Client portal login fails due to incorrect password hashing comparison",
    "description": "The client authentication service raises a ValueError during password verification because the stored hash is None. This occurs when a newly registered user attempts to log in immediately after registration without proper confirmation flow.",
    "test_name": "tests/unit/test_client_portal.py::test_login_newly_registered_client",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/client_portal/services.py\", line 78, in authenticate_client\n    if not verify_password(password, client.hashed_password):\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/app/mortgage_underwriting/common/security.py\", line 32, in verify_password\n    return pwd_context.verify(plain_password, hashed_password)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/passlib/context.py\", line 2345, in verify\n    return self._context.verify(secret, hash, **kwds)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.12/site-packages/passlib/context.py\", line 1079, in verify\n    raise ValueError(\"hash must not be None\")\nValueError: hash must not be None",
    "error_message": "hash must not be None",
    "affected_code": [
      "mortgage_underwriting/modules/client_portal/services.py",
      "line 78"
    ],
    "suggested_fix": "Ensure that the client registration process sets a default empty string or triggers immediate hashing of the provided password before saving the client object. Alternatively, validate that hashed_password is not null before attempting verification.",
    "severity": "high"
  },
  {
    "title": "Client profile update endpoint allows unauthorized modification of sensitive fields",
    "description": "An integration test reveals that clients can modify their own SIN and DOB through the profile update endpoint, violating PIPEDA encryption and immutability rules. The route does not filter out restricted fields from the input payload.",
    "test_name": "tests/integration/test_client_portal_integration.py::test_client_cannot_update_sin_or_dob",
    "error_type": "AssertionError",
    "stack_trace": "tests/integration/test_client_portal_integration.py:120: in test_client_cannot_update_sin_or_dob\n    assert response.json()['sin'] == original_sin\nE   AssertionError: assert '***-***-***' != '123-456-789'",
    "error_message": "assert '***-***-***' != '123-456-789'",
    "affected_code": [
      "mortgage_underwriting/modules/client_portal/routes.py",
      "line 65"
    ],
    "suggested_fix": "Filter incoming request data in the PATCH /profile endpoint to exclude restricted fields like 'sin' and 'dob'. Add explicit validation in the schema or service layer to reject updates to these fields.",
    "severity": "high"
  },
  {
    "title": "Client session timeout not enforced correctly in security middleware",
    "description": "Session tokens are still accepted beyond the configured expiration time due to improper datetime comparison logic in the JWT decoding step. Sessions remain valid indefinitely, posing a significant security risk.",
    "test_name": "tests/unit/test_client_portal.py::test_expired_session_rejected",
    "error_type": "AssertionError",
    "stack_trace": "tests/unit/test_client_portal.py:88: in test_expired_session_rejected\n    assert response.status_code == 401\nE   AssertionError: assert 200 == 401",
    "error_message": "assert 200 == 401",
    "affected_code": [
      "mortgage_underwriting/modules/client_portal/security.py",
      "line 42"
    ],
    "suggested_fix": "Correct the JWT expiration check by ensuring decoded['exp'] is compared as UTC timestamp against current UTC time using datetime.utcnow().timestamp(). Ensure pyjwt.decode uses options={'verify_exp': True}",
    "severity": "critical"
  },
  {
    "title": "Missing index on email column causes slow query performance in client lookup",
    "description": "Performance testing shows that client retrieval based on email takes over 2 seconds for datasets exceeding 10k records. Profiling confirms lack of database index on the email field in Client model.",
    "test_name": "tests/integration/test_client_portal_performance.py::test_client_email_lookup_speed",
    "error_type": "TimeoutError",
    "stack_trace": "tests/integration/test_client_portal_performance.py:45: in test_client_email_lookup_speed\n    response = client.get(f\"/api/v1/client?email={test_email}\")\nE   TimeoutError: Request timed out after 5 seconds",
    "error_message": "Request timed out after 5 seconds",
    "affected_code": [
      "mortgage_underwriting/modules/client_portal/models.py",
      "line 22"
    ],
    "suggested_fix": "Add Index('ix_clients_email', email) to the Client model definition. Run Alembic migration to apply index to PostgreSQL table.",
    "severity": "high"
  },
  {
    "title": "Audit trail missing for client document uploads",
    "description": "Uploaded documents do not have corresponding audit entries in the DocumentAuditLog model, violating FINTRAC requirements for immutable transaction records. No created_at or created_by metadata captured.",
    "test_name": "tests/unit/test_client_portal.py::test_document_upload_creates_audit_log_entry",
    "error_type": "AssertionError",
    "stack_trace": "tests/unit/test_client_portal.py:150: in test_document_upload_creates_audit_log_entry\n    assert audit_log_entry is not None\nE   AssertionError",
    "error_message": "assert audit_log_entry is not None",
    "affected_code": [
      "mortgage_underwriting/modules/client_portal/services.py",
      "line 112"
    ],
    "suggested_fix": "Modify document upload service method to insert a new entry into DocumentAuditLog upon successful save. Include fields: document_id, action='UPLOAD', created_at, created_by=user.id",
    "severity": "high"
  }
]
```