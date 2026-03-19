```json
[
  {
    "title": "Admin session expiration not enforced in service layer",
    "description": "Session validation does not check for expired sessions, allowing access with stale tokens.",
    "test_name": "tests/unit/test_admin_panel.py::test_expired_session_raises_unauthorized",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/tests/unit/test_admin_panel.py\", line 78, in test_expired_session_raises_unauthorized\n    assert exc_info.value.status_code == 401\nAssertionError: assert 200 == 401",
    "error_message": "Expected HTTP 401 for expired session but received 200 OK",
    "affected_code": [
      "mortgage_underwriting/modules/admin_panel/services.py",
      "line 32"
    ],
    "suggested_fix": "Add datetime comparison against expires_at field before returning valid session",
    "severity": "high"
  },
  {
    "title": "Admin role permissions incorrectly allow deletion of immutable audit trails",
    "description": "DELETE request to /admin/audit-log succeeds despite regulatory requirement for immutability (FINTRAC).",
    "test_name": "tests/integration/test_admin_panel_integration.py::test_delete_audit_log_fails",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/tests/integration/test_admin_panel_integration.py\", line 112, in test_delete_audit_log_fails\n    assert response.status_code == 403\nAssertionError: assert 200 == 403",
    "error_message": "Audit log deletion returned 200 instead of forbidden status",
    "affected_code": [
      "mortgage_underwriting/modules/admin_panel/routes.py",
      "line 67"
    ],
    "suggested_fix": "Remove DELETE route handler or enforce permission guard that always denies",
    "severity": "critical"
  },
  {
    "title": "PIPEDA violation: DOB decryption occurs outside secure context",
    "description": "DOB is decrypted and passed into logger without masking, violating PIPEDA encryption-at-rest rules.",
    "test_name": "tests/unit/test_admin_panel.py::test_dob_never_logged",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/tests/unit/test_admin_panel.py\", line 95, in test_dob_never_logged\n    mock_logger.assert_not_called_with(dob_value)\n  File \"unittest.mock.py\", line 897, in assert_not_called_with\n    raise ValueError(f\"Unexpected call: {call_args}\")\nValueError: Unexpected call: call('Decrypting DOB:', '1985-06-15')",
    "error_message": "DOB value was logged during decryption process",
    "affected_code": [
      "mortgage_underwriting/modules/admin_panel/services.py",
      "line 115"
    ],
    "suggested_fix": "Refactor decrypt_user_dob() to exclude logging raw values; ensure structlog filter blocks PII fields",
    "severity": "critical"
  },
  {
    "title": "Decimal precision loss detected in admin dashboard metrics",
    "description": "Aggregated financial summary uses float internally causing rounding inconsistencies.",
    "test_name": "tests/unit/test_admin_panel.py::test_dashboard_metrics_precision",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/tests/unit/test_admin_panel.py\", line 130, in test_dashboard_metrics_precision\n    assert total == Decimal('100000.00')\nAssertionError: Decimal('99999.9998') != Decimal('100000.00')",
    "error_message": "Total metric shows precision drift due to intermediate float usage",
    "affected_code": [
      "mortgage_underwriting/modules/admin_panel/services.py",
      "line 203"
    ],
    "suggested_fix": "Replace internal float operations with Decimal throughout _calculate_summary_stats()",
    "severity": "high"
  },
  {
    "title": "Missing updated_at enforcement causes audit inconsistency",
    "description": "Model allows manual override of updated_at field breaking audit integrity rule.",
    "test_name": "tests/unit/test_admin_panel.py::test_updated_at_auto_override_blocked",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/tests/unit/test_admin_panel.py\", line 155, in test_updated_at_auto_override_blocked\n    assert obj.updated_at == original_time\nAssertionError: datetime.datetime(2026, 3, 1, 12, 0) != datetime.datetime(2026, 3, 1, 11, 45)",
    "error_message": "updated_at field manually overridden instead of auto-updating",
    "affected_code": [
      "mortgage_underwriting/modules/admin_panel/models.py",
      "line 44"
    ],
    "suggested_fix": "Set server_default=func.now() and onupdate=func.now() on updated_at column definition",
    "severity": "medium"
  }
]
```