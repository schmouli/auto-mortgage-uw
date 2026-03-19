```json
[
  {
    "title": "GDS Calculation fails for negative gross income values",
    "description": "The GDS calculation service raises a ValueError when provided with negative gross income, which is not handled gracefully. This violates OSFI B-20 expectations that all inputs should be sanitized before financial computation.",
    "test_name": "tests/unit/test_underwriting_engine.py::test_gds_with_negative_gross_income",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/opt/testing/tests/unit/test_underwriting_engine.py\", line 123, in test_gds_with_negative_gross_income\n    result = await calculate_gds(session, input_data)\n  File \"/opt/mortgage_underwriting/modules/underwriting_engine/services.py\", line 47, in calculate_gds\n    raise ValueError(\"Gross income cannot be negative\")\nValueError: Gross income cannot be negative",
    "error_message": "Gross income cannot be negative",
    "affected_code": [
      "mortgage_underwriting/modules/underwriting_engine/services.py",
      "line 47"
    ],
    "suggested_fix": "Implement input validation at the schema level using Pydantic to reject negative income values early, preventing invalid data from reaching business logic layers.",
    "severity": "high"
  },
  {
    "title": "Missing updated_at field causes DB integrity error during insert",
    "description": "Model 'Applicant' does not include an 'updated_at' column despite regulatory requirement for audit fields on all models. Causes IntegrityError on insert due to NOT NULL constraint.",
    "test_name": "tests/integration/test_applicant_model.py::test_create_applicant_missing_updated_at",
    "error_type": "IntegrityError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/opt/testing/tests/integration/test_applicant_model.py\", line 56, in test_create_applicant_missing_updated_at\n    db.add(applicant)\n    await db.commit()\nsqlalchemy.exc.IntegrityError: null value in column \"updated_at\" violates not-null constraint",
    "error_message": "null value in column \"updated_at\" violates not-null constraint",
    "affected_code": [
      "mortgage_underwriting/modules/applicant/models.py",
      "line 22"
    ],
    "suggested_fix": "Add updated_at field with server_default=func.now() and onupdate=func.now(). Ensure Alembic migration reflects this addition without modifying prior migrations.",
    "severity": "critical"
  },
  {
    "title": "PIPEDA Violation: DOB exposed in logs via exception message",
    "description": "DOB field was included directly in exception message when parsing failed, violating PIPEDA encryption rules. Detected through log capture in testing environment.",
    "test_name": "tests/unit/test_security_compliance.py::test_dob_not_logged_on_parse_error",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/opt/testing/tests/unit/test_security_compliance.py\", line 89, in test_dob_not_logged_on_parse_error\n    assert '1985-06-15' not in captured_logs.text\nAssertionError",
    "error_message": "assert '1985-06-15' not in captured_logs.text",
    "affected_code": [
      "mortgage_underwriting/modules/applicant/schemas.py",
      "line 31"
    ],
    "suggested_fix": "Sanitize sensitive data before including in exceptions or logs. Use generic placeholders like '<REDACTED>' for PII fields in debug output.",
    "severity": "critical"
  },
  {
    "title": "Float used instead of Decimal for interest rate in CMHC premium lookup",
    "description": "Interest rates were stored as floats causing incorrect CMHC premium tier selection due to floating point precision loss. Impacts accuracy of insurance cost estimation.",
    "test_name": "tests/unit/test_cmhc_insurance.py::test_interest_rate_precision_loss",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/opt/testing/tests/unit/test_cmhc_insurance.py\", line 77, in test_interest_rate_precision_loss\n    expected = Decimal('0.0310')\n    actual = get_premium_tier(ltv=Decimal('87.5'), rate=float(0.0475))\nAssertionError: Decimal('0.0310') != Decimal('0.030999999999999996')",
    "error_message": "Decimal('0.0310') != Decimal('0.030999999999999996')",
    "affected_code": [
      "mortgage_underwriting/modules/cmhc/services.py",
      "line 23"
    ],
    "suggested_fix": "Replace float usage with Decimal throughout financial computations. Enforce strict typing in Pydantic models and service functions.",
    "severity": "high"
  },
  {
    "title": "Foreign key missing ondelete behavior leads to orphaned records",
    "description": "Foreign key relationship between Application and Applicant lacks ondelete='CASCADE', leading to orphaned Applicant records after application deletion.",
    "test_name": "tests/integration/test_application_deletion_cascade.py::test_orphaned_applicants_after_delete",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/opt/testing/tests/integration/test_application_deletion_cascade.py\", line 44, in test_orphaned_applicants_after_delete\n    assert len(orphaned_applicants) == 0\nAssertionError",
    "error_message": "assert len(orphaned_applicants) == 0",
    "affected_code": [
      "mortgage_underwriting/modules/application/models.py",
      "line 35"
    ],
    "suggested_fix": "Update ForeignKey definitions to include ondelete='CASCADE'. Generate new Alembic revision to apply changes safely.",
    "severity": "medium"
  }
]
```