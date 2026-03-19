```json
[
  {
    "title": "Lender API submission fails due to missing required field 'institution_id'",
    "description": "The lender comparison service raises a ValidationError when attempting to submit a lender without the mandatory 'institution_id' field. This causes partial data insertion and inconsistent state.",
    "test_name": "tests/unit/test_lender_comparison.py::test_submit_lender_missing_institution_id",
    "error_type": "ValidationError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/lender_comparison/services.py\", line 78, in submit_lender\n    validated_data = LenderSubmitRequest(**data)\n  File \"pydantic/main.py\", line 342, in pydantic.main.BaseModel.__init__\npydantic.error_wrappers.ValidationError: 1 validation error for LenderSubmitRequest\ninstitution_id\n  field required (type=value_error.missing)",
    "error_message": "field required (type=value_error.missing)",
    "affected_code": [
      "mortgage_underwriting/modules/lender_comparison/schemas.py",
      "line 22"
    ],
    "suggested_fix": "Ensure that institution_id is marked as required in LenderSubmitRequest schema and add explicit null-check in service layer before model instantiation.",
    "severity": "high"
  },
  {
    "title": "Comparison engine returns incorrect rate ranking due to float precision loss",
    "description": "When comparing lenders with nearly identical interest rates (e.g., 4.75% vs 4.7501%), the sorting logic incorrectly ranks them because of floating point imprecision during decimal conversion.",
    "test_name": "tests/integration/test_lender_comparison_integration.py::test_compare_lenders_precision_handling",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/lender_comparison/services.py\", line 135, in compare_lenders\n    sorted_offers = sorted(offers, key=lambda x: x.rate)\nAssertionError: Expected [offer_a, offer_c, offer_b], got [offer_b, offer_a, offer_c]",
    "error_message": "Expected [offer_a, offer_c, offer_b], got [offer_b, offer_a, offer_c]",
    "affected_code": [
      "mortgage_underwriting/modules/lender_comparison/services.py",
      "line 135"
    ],
    "suggested_fix": "Replace raw float-based sorting with Decimal-aware comparison using quantized values or custom comparator enforcing fixed-point precision.",
    "severity": "high"
  },
  {
    "title": "Submission endpoint does not enforce FINTRAC threshold check for large transactions",
    "description": "Submitting a mortgage application with total_loan_amount exceeding $10,000 fails to trigger the required transaction_type flagging mechanism per FINTRAC compliance rules.",
    "test_name": "tests/unit/test_submission.py::test_fintrac_large_transaction_flagging",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/submission/services.py\", line 92, in process_submission\n    assert flagged == True, f\"Transaction over ${threshold} should be flagged\"\nAssertionError: Transaction over $10000 should be flagged",
    "error_message": "Transaction over $10000 should be flagged",
    "affected_code": [
      "mortgage_underwriting/modules/submission/services.py",
      "line 92"
    ],
    "suggested_fix": "Implement conditional logic in submission processing to set transaction_type='large' when total_loan_amount > 10000 and log audit event accordingly.",
    "severity": "high"
  },
  {
    "title": "Encrypted PII leaked into debug logs during submission failure",
    "description": "When submission validation fails, some personal information including date_of_birth was logged in cleartext despite encryption-at-rest policy (PIPEDA violation).",
    "test_name": "tests/unit/test_submission.py::test_encryption_log_leak_prevention",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/common/security.py\", line 45, in decrypt_pii\n    raise ValueError(\"DOB exposed in logs\")\nValueError: DOB exposed in logs",
    "error_message": "DOB exposed in logs",
    "affected_code": [
      "mortgage_underwriting/modules/submission/routes.py",
      "line 67"
    ],
    "suggested_fix": "Sanitize exception contexts and log messages by removing any PII fields before writing to logs; wrap sensitive operations in try-except blocks with scrubbed error reporting.",
    "severity": "critical"
  },
  {
    "title": "Database update hook omits updated_at timestamp on modification",
    "description": "Modifying existing lender offers fails to update the `updated_at` column automatically, violating audit requirements under OSFI/FINTRAC regulations.",
    "test_name": "tests/integration/test_lender_comparison_integration.py::test_updated_at_timestamp_propagation",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/lender_comparison/models.py\", line 102, in update_offer\n    assert self.updated_at != old_updated_at\nAssertionError",
    "error_message": "",
    "affected_code": [
      "mortgage_underwriting/modules/lender_comparison/models.py",
      "line 102"
    ],
    "suggested_fix": "Add server_default=func.now() and onupdate=func.now() to updated_at column definition in SQLAlchemy model declaration.",
    "severity": "high"
  }
]
```