```json
[
  {
    "title": "GDS Calculation fails for negative gross income input",
    "description": "The GDS calculation service raises a ValueError when passed negative gross income values, which should be handled gracefully with input validation.",
    "test_name": "tests/unit/test_underwriting_engine.py::test_gds_with_negative_gross_income",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_underwriting_engine.py\", line 45, in test_gds_with_negative_gross_income\n    result = calculate_gds(...)\n  File \"/app/mortgage_underwriting/modules/underwriting_engine/services.py\", line 67, in calculate_gds\n    raise ValueError(\"Gross income cannot be negative\")\nValueError: Gross income cannot be negative",
    "error_message": "Gross income cannot be negative",
    "affected_code": [
      "mortgage_underwriting/modules/underwriting_engine/services.py",
      "line 67"
    ],
    "suggested_fix": "Add explicit input validation at the start of calculate_gds to reject negative values early and return structured error response via custom exception.",
    "severity": "high"
  },
  {
    "title": "TDS ratio exceeds regulatory limit without triggering exception",
    "description": "TDS ratio computed as 46.2%, exceeding OSFI B-20 maximum of 44%, but no exception is raised during underwriting decision process.",
    "test_name": "tests/unit/test_underwriting_engine.py::test_tds_limit_violation_not_flagged",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_underwriting_engine.py\", line 78, in test_tds_limit_violation_not_flagged\n    assert decision.is_approved is False\nAssertionError",
    "error_message": "assert decision.is_approved is False",
    "affected_code": [
      "mortgage_underwriting/modules/underwriting_engine/services.py",
      "line 112"
    ],
    "suggested_fix": "Ensure that TDS >= 44% triggers denial or flags approval status correctly by adding conditional check post-calculation.",
    "severity": "high"
  },
  {
    "title": "LTV calculation returns incorrect decimal precision",
    "description": "Loan-to-value ratio calculated using float division instead of Decimal operations, causing precision loss in insurance eligibility logic.",
    "test_name": "tests/unit/test_underwriting_engine.py::test_ltv_precision_loss_on_division",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_underwriting_engine.py\", line 93, in test_ltv_precision_loss_on_division\n    assert ltv == Decimal('0.8375')\nAssertionError",
    "error_message": "assert ltv == Decimal('0.8375')",
    "affected_code": [
      "mortgage_underwriting/modules/underwriting_engine/models.py",
      "line 34"
    ],
    "suggested_fix": "Replace '/' operator with Decimal-based arithmetic (`from decimal import Decimal`) to preserve financial precision per CMHC compliance.",
    "severity": "high"
  },
  {
    "title": "Missing encryption of DOB field violates PIPEDA",
    "description": "Date of birth stored directly in model without encryption despite being classified as PII under PIPEDA regulations.",
    "test_name": "tests/integration/test_underwriting_engine_integration.py::test_dob_encryption_missing_in_db",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_underwriting_engine_integration.py\", line 52, in test_dob_encryption_missing_in_db\n    assert row.dob == raw_dob  # Should be encrypted!\nAssertionError",
    "error_message": "assert row.dob == raw_dob",
    "affected_code": [
      "mortgage_underwriting/modules/underwriting_engine/models.py",
      "line 21"
    ],
    "suggested_fix": "Implement encryption hook in SQLAlchemy model using common/security.py encrypt_pii() method before saving DOB.",
    "severity": "critical"
  },
  {
    "title": "Audit trail missing created_by field causes FINTRAC violation",
    "description": "Financial transaction records lack mandatory 'created_by' field required for immutable audit trails under FINTRAC guidelines.",
    "test_name": "tests/unit/test_underwriting_engine.py::test_transaction_audit_created_by_missing",
    "error_type": "KeyError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_underwriting_engine.py\", line 107, in test_transaction_audit_created_by_missing\n    assert tx['created_by'] is not None\nKeyError: 'created_by'",
    "error_message": "'created_by'",
    "affected_code": [
      "mortgage_underwriting/modules/underwriting_engine/models.py",
      "line 45"
    ],
    "suggested_fix": "Add created_by column to Transaction model with proper constraints and populate it from authenticated user context.",
    "severity": "high"
  }
]
```