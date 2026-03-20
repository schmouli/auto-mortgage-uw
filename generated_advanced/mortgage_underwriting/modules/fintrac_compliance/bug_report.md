```json
[
  {
    "title": "Missing Transaction Type Flag for Large Financial Transactions",
    "description": "Test failure indicates that transactions exceeding CAD $10,000 do not trigger the required explicit transaction type flag as mandated by FINTRAC compliance rules.",
    "test_name": "tests/unit/test_fintrac_compliance.py::test_large_transaction_requires_flag",
    "error_type": "AssertionError",
    "stack_trace": "tests/unit/test_fintrac_compliance.py:45: in test_large_transaction_requires_flag\n    assert transaction.transaction_type_flag is not None\nAssertionError",
    "error_message": "assert None is not None",
    "affected_code": [
      "mortgage_underwriting/modules/fintrac/models.py",
      "line 32"
    ],
    "suggested_fix": "Update the Transaction model to enforce setting of transaction_type_flag during creation when amount exceeds CAD $10,000. Add validation logic in service layer.",
    "severity": "high"
  },
  {
    "title": "Audit Trail Fields Not Present in Transaction Model",
    "description": "FINTRAC requires immutable audit trails including created_at and created_by fields. These are missing from the Transaction model causing test failures related to regulatory compliance checks.",
    "test_name": "tests/unit/test_fintrac_compliance.py::test_audit_trail_fields_present",
    "error_type": "KeyError",
    "stack_trace": "tests/unit/test_fintrac_compliance.py:30: in test_audit_trail_fields_present\n    assert hasattr(transaction, 'created_at')\nKeyError: 'created_at'",
    "error_message": "'created_at'",
    "affected_code": [
      "mortgage_underwriting/modules/fintrac/models.py",
      "line 18"
    ],
    "suggested_fix": "Add created_at (DateTime), created_by (String), updated_at (DateTime) fields to Transaction model. Ensure they're populated on creation and immutable post-insert.",
    "severity": "high"
  },
  {
    "title": "Identity Verification Logging Missing",
    "description": "FINTRAC mandates logging identity verification events. Tests show this functionality is either unimplemented or improperly recorded, leading to compliance gaps.",
    "test_name": "tests/unit/test_fintrac_compliance.py::test_log_identity_verification_event",
    "error_type": "AttributeError",
    "stack_trace": "tests/unit/test_fintrac_compliance.py:60: in test_log_identity_verification_event\n    result = services.log_identity_verification(user_id)\nAttributeError: module 'mortgage_underwriting.modules.fintrac.services' has no attribute 'log_identity_verification'",
    "error_message": "module 'mortgage_underwriting.modules.fintrac.services' has no attribute 'log_identity_verification'",
    "affected_code": [
      "mortgage_underwriting/modules/fintrac/services.py",
      "N/A"
    ],
    "suggested_fix": "Implement log_identity_verification() function in services.py which writes to a dedicated audit table with user_id, timestamp, method_used, and status.",
    "severity": "high"
  }
]
```