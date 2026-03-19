```json
[
  {
    "title": "DecisionService fails to enforce OSFI B-20 stress test for high-ratio mortgages",
    "description": "Test failure indicates that DecisionService does not apply the OSFI B-20 mandated stress test using qualifying_rate = max(contract_rate + 2%, 5.25%) during eligibility determination. This leads to incorrect approval decisions for high-ratio applicants.",
    "test_name": "tests/unit/test_decision_service.py::test_stress_test_not_applied_for_high_ratio_mortgage",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_decision_service.py\", line 120, in test_stress_test_not_applied_for_high_ratio_mortgage\n    assert decision.status == 'denied'\nAssertionError: assert 'approved' == 'denied'",
    "error_message": "assert 'approved' == 'denied'",
    "affected_code": [
      "mortgage_underwriting/modules/decision_service/services.py",
      "line 67"
    ],
    "suggested_fix": "Modify _evaluate_eligibility() in services.py to calculate and compare GDS/TDS against stress-tested rates using qualifying_rate = max(contract_rate + 2%, 5.25%). Ensure audit logs capture both contract and stress-tested ratios.",
    "severity": "high"
  },
  {
    "title": "Missing CMHC insurance premium calculation for LTV between 80.01%-85%",
    "description": "The decision service incorrectly approves a mortgage with an LTV of 83% without requiring CMHC insurance or adding the corresponding premium cost to total debt obligations, violating CMHC regulatory compliance.",
    "test_name": "tests/unit/test_decision_service.py::test_cmhc_insurance_missing_from_debt_obligations",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_decision_service.py\", line 89, in test_cmhc_insurance_missing_from_debt_obligations\n    assert Decimal('3200.00') < result.total_monthly_debt\nAssertionError: assert Decimal('3200.00') < Decimal('3150.00')",
    "error_message": "assert Decimal('3200.00') < Decimal('3150.00')",
    "affected_code": [
      "mortgage_underwriting/modules/decision_service/services.py",
      "line 102"
    ],
    "suggested_fix": "Implement CMHC premium lookup based on LTV thresholds and add calculated monthly premium to total_monthly_debt before determining affordability. Premium tiers: 80.01–85% = 2.80%, 85.01–90% = 3.10%, 90.01–95% = 4.00%.",
    "severity": "high"
  },
  {
    "title": "PIPEDA violation: DOB exposed in debug log during identity verification",
    "description": "DOB is being logged directly during identity verification step, violating PII protection standards under PIPEDA. Logs must never contain sensitive personal information such as date of birth.",
    "test_name": "tests/integration/test_decision_service_integration.py::test_dob_exposed_in_debug_log",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/integration/test_decision_service_integration.py\", line 56, in test_dob_exposed_in_debug_log\n    raise ValueError(\"Found DOB in log output\")\nValueError: Found DOB in log output",
    "error_message": "Found DOB in log output",
    "affected_code": [
      "mortgage_underwriting/modules/decision_service/services.py",
      "line 34"
    ],
    "suggested_fix": "Replace direct logging of applicant data with sanitized placeholders. Use secure hash (e.g., SHA256) for correlation IDs derived from SIN but do not expose raw DOB or SIN in logs.",
    "severity": "critical"
  },
  {
    "title": "FINTRAC audit trail missing created_by field for transaction records",
    "description": "Generated transaction records lack the mandatory 'created_by' field required by FINTRAC regulations for maintaining immutable audit trails. All financial transactions must include creation metadata.",
    "test_name": "tests/unit/test_decision_service.py::test_fintrac_audit_fields_missing",
    "error_type": "KeyError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_decision_service.py\", line 150, in test_fintrac_audit_fields_missing\n    assert 'created_by' in transaction.model_dump()\nKeyError: 'created_by'",
    "error_message": "'created_by'",
    "affected_code": [
      "mortgage_underwriting/modules/decision_service/models.py",
      "line 28"
    ],
    "suggested_fix": "Add 'created_by' field to TransactionModel schema and populate it with authenticated user identifier upon record creation. Ensure all model instances inherit BaseAuditModel which includes created_at, updated_at, and created_by fields.",
    "severity": "high"
  }
]
```