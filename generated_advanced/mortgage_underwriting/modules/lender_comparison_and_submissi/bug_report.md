```json
[
  {
    "title": "Lender rate comparison fails due to precision loss in Decimal conversion",
    "description": "The lender_comparison service computes effective rates using Decimal operations. However, during testing, it was observed that converting float values directly into Decimal leads to imprecise representations which affect final comparisons.",
    "test_name": "tests/unit/test_lender_comparison.py::test_compare_lenders_precision_loss",
    "error_type": "AssertionError",
    "stack_trace": "File \"mortgage_underwriting/modules/lender_comparison/services.py\", line 67, in compare_lenders\n    effective_rate = Decimal(rate)\nAssertionError: Decimal('0.04999999999999999999999999999') != Decimal('0.05')",
    "error_message": "Decimal('0.04999999999999999999999999999') != Decimal('0.05')",
    "affected_code": [
      "mortgage_underwriting/modules/lender_comparison/services.py",
      "line 67"
    ],
    "suggested_fix": "Ensure all rate inputs are passed as string literals to Decimal constructor to prevent floating point inaccuracies. Example: Decimal('0.05') instead of Decimal(0.05)",
    "severity": "high"
  },
  {
    "title": "Submission creation fails when applicant has multiple loans exceeding threshold",
    "description": "In submission creation logic, applicants with more than one existing loan were causing unexpected behavior because total_debt wasn't being calculated correctly across all linked loans.",
    "test_name": "tests/integration/test_submission_integration.py::test_create_submission_multiple_loans",
    "error_type": "ValueError",
    "stack_trace": "File \"mortgage_underwriting/modules/submission/services.py\", line 123, in calculate_total_debt\n    raise ValueError(\"Invalid debt sum encountered\")\nValueError: Invalid debt sum encountered",
    "error_message": "Invalid debt sum encountered",
    "affected_code": [
      "mortgage_underwriting/modules/submission/services.py",
      "line 123"
    ],
    "suggested_fix": "Refactor calculate_total_debt method to safely accumulate debts from related Loan entities ensuring proper null checks and default zero handling.",
    "severity": "high"
  },
  {
    "title": "Missing index on submission.status causes slow query performance",
    "description": "Querying submissions by status is taking over 500ms due to lack of database index on the status column. This affects both API response times and background job execution speed.",
    "test_name": "N/A (performance observation)",
    "error_type": "PerformanceWarning",
    "stack_trace": "",
    "error_message": "Slow query detected for filtering submissions by status without an index.",
    "affected_code": [
      "mortgage_underwriting/modules/submission/models.py",
      "Submission.status"
    ],
    "suggested_fix": "Add database index to Submission.status column via new migration script.",
    "severity": "high"
  },
  {
    "title": "Submission schema allows optional employment_history despite regulatory requirement",
    "description": "PIPEDA mandates minimal data collection strictly necessary for underwriting decisions. The current SubmissionCreate schema accepts optional employment_history even though it's not used in decisioning flow.",
    "test_name": "tests/unit/test_submission_schemas.py::test_minimal_data_schema_validation",
    "error_type": "ValidationError",
    "stack_trace": "File \"mortgage_underwriting/modules/submission/schemas.py\", line 34, in SubmissionCreate\n    employment_history: Optional[List[EmploymentHistory]]\npydantic_core._pydantic_core.ValidationError: Field 'employment_history' should be excluded per PIPEDA compliance rules",
    "error_message": "Field 'employment_history' should be excluded per PIPEDA compliance rules",
    "affected_code": [
      "mortgage_underwriting/modules/submission/schemas.py",
      "line 34"
    ],
    "suggested_fix": "Remove employment_history field from SubmissionCreate DTO or explicitly exclude it unless explicitly needed for a verified business purpose.",
    "severity": "medium"
  },
  {
    "title": "Lender comparison engine does not handle lender rate updates gracefully",
    "description": "During integration testing, updating lender rates dynamically caused stale cached values leading to incorrect comparisons until cache expiry.",
    "test_name": "tests/integration/test_lender_comparison_integration.py::test_update_lender_rates_cache_invalidation",
    "error_type": "AssertionError",
    "stack_trace": "File \"mortgage_underwriting/modules/lender_comparison/services.py\", line 89, in update_lender_rate\n    assert old_rate != new_rate\nAssertionError",
    "error_message": "old_rate == new_rate after update",
    "affected_code": [
      "mortgage_underwriting/modules/lender_comparison/services.py",
      "line 89"
    ],
    "suggested_fix": "Implement cache invalidation strategy upon successful rate updates so subsequent comparisons reflect latest data.",
    "severity": "medium"
  }
]
```