```json
[
  {
    "title": "Missing Transaction Type Flag for Large Transactions",
    "description": "Test failure indicates that financial transactions exceeding CAD $10,000 do not trigger the required explicit transaction type flag as mandated by FINTRAC regulations.",
    "test_name": "tests/unit/test_fintrac_compliance.py::test_transaction_over_10k_requires_flag",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_fintrac_compliance.py\", line 32, in test_transaction_over_10k_requires_flag\n    assert result.transaction_type_flag is not None\nAssertionError",
    "error_message": "assert result.transaction_type_flag is not None",
    "affected_code": [
      "mortgage_underwriting/modules/fintrac/models.py",
      "line 42"
    ],
    "suggested_fix": "Update Transaction model to automatically set transaction_type_flag based on amount during creation or modification",
    "severity": "high"
  },
  {
    "title": "Audit Trail Not Immutable for Financial Records",
    "description": "Modification of financial transaction records allowed without preserving audit trail history, violating FINTRAC's immutability requirement.",
    "test_name": "tests/unit/test_fintrac_compliance.py::test_audit_trail_immutability_enforced",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_fintrac_compliance.py\", line 58, in test_audit_trail_immutability_enforced\n    assert updated.created_at == original.created_at\nAssertionError",
    "error_message": "assert updated.created_at == original.created_at",
    "affected_code": [
      "mortgage_underwriting/modules/fintrac/services.py",
      "line 76"
    ],
    "suggested_fix": "Implement soft-delete pattern and versioned updates; prevent direct modifications to audit fields like created_at",
    "severity": "high"
  },
  {
    "title": "Identity Verification Event Not Logged",
    "description": "Identity verification process does not log events as required under FINTRAC guidelines, leading to compliance gap.",
    "test_name": "tests/unit/test_fintrac_compliance.py::test_identity_verification_logged",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_fintrac_compliance.py\", line 84, in test_identity_verification_logged\n    assert event_log.exists()\nAssertionError",
    "error_message": "assert event_log.exists()",
    "affected_code": [
      "mortgage_underwriting/modules/fintrac/services.py",
      "line 112"
    ],
    "suggested_fix": "Ensure identity verification service calls logging utility with structured FINTRAC event schema",
    "severity": "high"
  },
  {
    "title": "Record Retention Policy Violation",
    "description": "Financial transaction records older than 5 years are being deleted or archived improperly, breaching FINTRAC’s mandatory 5-year retention rule.",
    "test_name": "tests/integration/test_fintrac_integration.py::test_five_year_retention_enforced",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_fintrac_integration.py\", line 41, in test_five_year_retention_enforced\n    assert len(old_records) > 0\nAssertionError",
    "error_message": "assert len(old_records) > 0",
    "affected_code": [
      "mortgage_underwriting/modules/fintrac/services.py",
      "line 135"
    ],
    "suggested_fix": "Modify cleanup job logic to exclude records within 5-year window from deletion/archival routines",
    "severity": "high"
  }
]
```