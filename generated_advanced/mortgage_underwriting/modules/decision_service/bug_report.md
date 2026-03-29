```json
[
  {
    "title": "Decision Service returns approval for invalid GDS ratio",
    "description": "Test failed because decision engine approved mortgage despite GDS exceeding OSFI B-20 maximum of 39%. The calculated GDS was 41.5%, which should have resulted in rejection.",
    "test_name": "tests/unit/test_decision_service.py::test_invalid_gds_ratio_rejected",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_decision_service.py\", line 87, in test_invalid_gds_ratio_rejected\n    assert result.status == DecisionStatus.REJECTED\nAssertionError: assert <DecisionStatus.APPROVED: 'APPROVED'> == <DecisionStatus.REJECTED: 'REJECTED'>",
    "error_message": "assert <DecisionStatus.APPROVED: 'APPROVED'> == <DecisionStatus.REJECTED: 'REJECTED'>",
    "affected_code": [
      "mortgage_underwriting/modules/decision_service/services.py",
      "line 62"
    ],
    "suggested_fix": "Ensure GDS validation occurs before final decision is made. Add explicit check: if gds > Decimal('0.39'): raise GDSLimitExceededError().",
    "severity": "high"
  },
  {
    "title": "TDS calculation does not apply stress test rate",
    "description": "TDS calculation used contract rate instead of required OSFI stress test rate (max(current_rate + 2%, 5.25%)). This violates regulatory compliance.",
    "test_name": "tests/unit/test_decision_service.py::test_tds_stress_test_applied",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_decision_service.py\", line 113, in test_tds_stress_test_applied\n    assert tds_result.qualifying_rate == Decimal('5.25')\nAssertionError: assert Decimal('4.75') == Decimal('5.25')",
    "error_message": "assert Decimal('4.75') == Decimal('5.25')",
    "affected_code": [
      "mortgage_underwriting/modules/decision_service/services.py",
      "line 38"
    ],
    "suggested_fix": "Update _calculate_tds() method to compute qualifying_rate as max(contract_rate + 2%, 5.25%) before applying to debt calculations.",
    "severity": "high"
  },
  {
    "title": "Insurance requirement ignored when LTV exceeds 80%",
    "description": "System approved application without requiring CMHC insurance for LTV = 87.3%. According to CMHC rules, insurance is mandatory above 80% LTV threshold.",
    "test_name": "tests/unit/test_decision_service.py::test_cmhc_insurance_required_above_80_percent_ltv",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_decision_service.py\", line 142, in test_cmhc_insurance_required_above_80_percent_ltv\n    assert result.insurance_required is True\nAssertionError: assert False is True",
    "error_message": "assert False is True",
    "affected_code": [
      "mortgage_underwriting/modules/decision_service/models.py",
      "line 29"
    ],
    "suggested_fix": "In DecisionInput model, ensure insurance_required flag is computed using: self.ltv > Decimal('0.80'). Also validate premium tier mapping logic.",
    "severity": "high"
  },
  {
    "title": "PIPEDA violation: DOB leaked into logs during identity verification",
    "description": "DOB field appeared in debug log statement within identity verification process, violating PIPEDA encryption-at-rest and logging restrictions.",
    "test_name": "tests/integration/test_decision_service_integration.py::test_no_pii_in_logs",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_decision_service_integration.py\", line 65, in test_no_pii_in_logs\n    assert 'dob' not in captured_log_text\nValueError: substring not found",
    "error_message": "substring not found",
    "affected_code": [
      "mortgage_underwriting/modules/decision_service/services.py",
      "line 112"
    ],
    "suggested_fix": "Remove or sanitize DOB from log statements. Replace with hash(identifier) or omit entirely from logs.",
    "severity": "critical"
  },
  {
    "title": "Negative income values cause unhandled exception in service layer",
    "description": "Passing negative gross annual income caused uncaught ValueError deep in financial calculation logic instead of proper input validation.",
    "test_name": "tests/unit/test_decision_service.py::test_negative_income_handling",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_decision_service.py\", line 95, in test_negative_income_handling\n    await decision_service.evaluate(input_data)\n  File \"/app/mortgage_underwriting/modules/decision_service/services.py\", line 74, in evaluate\n    gds = calculate_gds(...)\n  File \"/app/mortgage_underwriting/common/calculators.py\", line 22, in calculate_gds\n    return total_housing_costs / gross_annual_income\nZeroDivisionError: float division by zero",
    "error_message": "float division by zero",
    "affected_code": [
      "mortgage_underwriting/modules/decision_service/services.py",
      "line 74"
    ],
    "suggested_fix": "Validate all monetary inputs >= 0 before processing. Raise InvalidInputError for negative values early in the flow.",
    "severity": "medium"
  }
]
```