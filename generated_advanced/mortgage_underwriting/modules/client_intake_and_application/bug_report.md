```json
[
  {
    "title": "Client SIN Not Encrypted Before Save",
    "description": "The client's SIN is saved in plain text instead of being encrypted per PIPEDA compliance. This violates encryption-at-rest requirements.",
    "test_name": "tests/unit/test_client_intake.py::test_save_client_encrypts_sin",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/tests/unit/test_client_intake.py\", line 67, in test_save_client_encrypts_sin\n    assert client.sin != plain_sin\nAssertionError",
    "error_message": "assert '123456789' != '123456789'",
    "affected_code": [
      "mortgage_underwriting/modules/client_intake/models.py",
      "line 32"
    ],
    "suggested_fix": "Modify the Client model's setter for SIN to call encrypt_pii() from common/security.py before saving.",
    "severity": "high"
  },
  {
    "title": "DOB Appears in Logs During Validation Error",
    "description": "Client DOB was found in exception log output during validation failure, violating PIPEDA logging restrictions.",
    "test_name": "tests/unit/test_client_intake.py::test_dob_not_logged_on_validation_error",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/tests/unit/test_client_intake.py\", line 82, in test_dob_not_logged_on_validation_error\n    assert 'dob' not in caplog.text.lower()\nAssertionError",
    "error_message": "assert 'dob' not in '...invalidclient(dob=datetime.date(1980, 1, 1))...'",
    "affected_code": [
      "mortgage_underwriting/modules/client_intake/services.py",
      "line 55"
    ],
    "suggested_fix": "Ensure sensitive fields like DOB are excluded from structured logs using custom serializer or scrubber utility.",
    "severity": "high"
  },
  {
    "title": "Missing Index on Client Email Column Causes Slow Query",
    "description": "Querying clients by email takes over 2 seconds due to missing index, causing timeout in integration tests.",
    "test_name": "tests/integration/test_client_intake_integration.py::test_find_client_by_email_performance",
    "error_type": "TimeoutError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/tests/integration/test_client_intake_integration.py\", line 43, in test_find_client_by_email_performance\n    result = await service.find_by_email(session, \"john.doe@example.com\")\n  File \"/app/mortgage_underwriting/modules/client_intake/services.py\", line 72, in find_by_email\n    return await session.execute(select(Client).where(Client.email == email)).scalar_one_or_none()\nTimeoutError: Query exceeded maximum execution time",
    "error_message": "Query exceeded maximum execution time",
    "affected_code": [
      "mortgage_underwriting/modules/client_intake/models.py",
      "line 25"
    ],
    "suggested_fix": "Add an index to the email column in the Client model: email = Column(String, unique=True, index=True)",
    "severity": "high"
  },
  {
    "title": "Hardcoded Max Clients Per Page Limit Should Be Configurable",
    "description": "Pagination limit is hardcoded to 100 in route handler, which should come from configuration settings.",
    "test_name": "tests/unit/test_client_intake.py::test_list_clients_respects_configurable_limit",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/tests/unit/test_client_intake.py\", line 95, in test_list_clients_respects_configurable_limit\n    assert response.json()['limit'] == app_settings.max_page_size\nAssertionError: assert 100 == 50",
    "error_message": "assert 100 == 50",
    "affected_code": [
      "mortgage_underwriting/modules/client_intake/routes.py",
      "line 38"
    ],
    "suggested_fix": "Replace hardcoded limit with dynamic value from common.config.AppSettings().max_page_size",
    "severity": "medium"
  }
]
```