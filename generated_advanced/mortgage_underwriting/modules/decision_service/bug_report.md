```json
[
  {
    "title": "DecisionService.calculate_gds_tds_ratio fails with ZeroDivisionError",
    "description": "The calculate_gds_tds_ratio method raises a ZeroDivisionError when gross_monthly_income is zero. This leads to unhandled exception during underwriting decision process.",
    "test_name": "tests/unit/test_decision_service.py::test_calculate_gds_tds_zero_income",
    "error_type": "ZeroDivisionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/opt/project/mortgage_underwriting/tests/unit/test_decision_service.py\", line 47, in test_calculate_gds_tds_zero_income\n    result = DecisionService.calculate_gds_tds_ratio(Decimal('0'), Decimal('1000'), Decimal('500'))\n  File \"/opt/project/mortgage_underwriting/modules/decision_service/services.py\", line 32, in calculate_gds_tds_ratio\n    gds = (housing_costs / gross_monthly_income) * 100\nZeroDivisionError: division by zero",
    "error_message": "division by zero",
    "affected_code": [
      "mortgage_underwriting/modules/decision_service/services.py",
      "line 32"
    ],
    "suggested_fix": "Add input validation to check for zero gross monthly income before performing division. Return default safe values or raise custom validation error.",
    "severity": "high"
  },
  {
    "title": "DecisionService.apply_stress_test uses hardcoded rate instead of dynamic lookup",
    "description": "apply_stress_test does not correctly apply OSFI B-20 stress test logic. It compares against fixed 5.25% rather than computing max(contract_rate + 2%, 5.25%)",
    "test_name": "tests/unit/test_decision_service.py::test_apply_stress_test_incorrect_logic",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/opt/project/mortgage_underwriting/tests/unit/test_decision_service.py\", line 68, in test_apply_stress_test_incorrect_logic\n    assert applied_rate == max(contract_rate + Decimal('0.02'), Decimal('0.0525'))\nAssertionError: assert Decimal('0.0525') == Decimal('0.0625')",
    "error_message": "assert Decimal('0.0525') == Decimal('0.0625')",
    "affected_code": [
      "mortgage_underwriting/modules/decision_service/services.py",
      "line 58"
    ],
    "suggested_fix": "Update apply_stress_test to compute qualifying rate using formula: max(contract_rate + 2%, 5.25%). Ensure compliance with OSFI B-20 regulatory requirement.",
    "severity": "high"
  },
  {
    "title": "DecisionService.validate_insurance_eligibility returns incorrect LTV thresholds",
    "description": "validate_insurance_eligibility incorrectly flags loans with LTV <= 80% as requiring insurance due to floating point precision loss during percentage comparisons.",
    "test_name": "tests/unit/test_decision_service.py::test_validate_insurance_eligibility_precision_loss",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/opt/project/mortgage_underwriting/tests/unit/test_decision_service.py\", line 92, in test_validate_insurance_eligibility_precision_loss\n    assert result['insurance_required'] is False\nAssertionError: assert True is False",
    "error_message": "assert True is False",
    "affected_code": [
      "mortgage_underwriting/modules/decision_service/services.py",
      "line 74"
    ],
    "suggested_fix": "Ensure all LTV calculations use Decimal type throughout the flow. Replace direct float comparisons with Decimal-aware threshold checks aligned with CMHC guidelines.",
    "severity": "high"
  },
  {
    "title": "Missing encryption for sensitive borrower data in logging statements",
    "description": "BorrowerService logs raw DOB and partial SIN without encryption/hashing which violates PIPEDA regulations. These fields should never appear in logs.",
    "test_name": "tests/integration/test_borrower_integration.py::test_log_redaction_for_sensitive_fields",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/opt/project/mortgage_underwriting/tests/integration/test_borrower_integration.py\", line 115, in test_log_redaction_for_sensitive_fields\n    raise ValueError(\"Sensitive field 'dob' found in logs\")\nValueError: Sensitive field 'dob' found in logs",
    "error_message": "Sensitive field 'dob' found in logs",
    "affected_code": [
      "mortgage_underwriting/modules/borrower/models.py",
      "line 28"
    ],
    "suggested_fix": "Implement automatic redaction mechanism in logging layer. Apply encryption/hash transformation via common/security.py utilities before any log emission involving personal identifiers.",
    "severity": "critical"
  }
]
```