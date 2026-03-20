```json
[
  {
    "title": "Lender comparison service returns incorrect premium calculation for high LTV loans",
    "description": "The lender_comparison service computes insurance premiums based on LTV ratios. For an LTV of 92%, the expected premium rate is 3.10% (tier: 85.01–90%), but the system returned 4.00%. This violates CMHC regulatory logic requiring precise tier mapping.",
    "test_name": "tests/unit/test_lender_comparison.py::test_insurance_premium_calculation_high_ltv",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_lender_comparison.py\", line 78, in test_insurance_premium_calculation_high_ltv\n    assert result.premium_rate == Decimal('3.10')\nAssertionError: assert Decimal('4.00') == Decimal('3.10')",
    "error_message": "assert Decimal('4.00') == Decimal('3.10')",
    "affected_code": [
      "mortgage_underwriting/modules/lender_comparison/services.py",
      "line 62"
    ],
    "suggested_fix": "Review and correct the LTV tier conditionals in `_calculate_insurance_premium()` to ensure accurate bracket matching using strict inequalities per CMHC rules.",
    "severity": "high"
  },
  {
    "title": "Submission endpoint fails to validate mandatory applicant SIN before encryption",
    "description": "Submitting a request without 'sin' field raises KeyError during encryption step instead of returning structured validation error. PII should be validated prior to processing.",
    "test_name": "tests/integration/test_submission_integration.py::test_submit_missing_sin_field",
    "error_type": "KeyError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_submission_integration.py\", line 112, in test_submit_missing_sin_field\n    response = client.post('/api/v1/submission/', json=payload)\n  File \"/app/mortgage_underwriting/modules/submission/routes.py\", line 34, in submit_application\n    await submission_service.create(data)\n  File \"/app/mortgage_underwriting/modules/submission/services.py\", line 48, in create\n    encrypted_sin = encrypt_pii(applicant['sin'])\nKeyError: 'sin'",
    "error_message": "KeyError: 'sin'",
    "affected_code": [
      "mortgage_underwriting/modules/submission/services.py",
      "line 48"
    ],
    "suggested_fix": "Add Pydantic schema validation with required=True for SIN field in submission DTOs (schemas.py), preventing KeyError by catching missing fields early.",
    "severity": "high"
  },
  {
    "title": "Underwriting stress test not applied in lender comparison scoring algorithm",
    "description": "Lender score calculation does not apply OSFI-mandated stress testing using qualifying_rate=max(contract_rate + 2%, 5.25%). As a result, scores may reflect unrealistic affordability scenarios.",
    "test_name": "tests/unit/test_lender_comparison.py::test_stress_test_not_applied_in_scoring",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_lender_comparison.py\", line 135, in test_stress_test_not_applied_in_scoring\n    assert score_with_stress != baseline_score\nAssertionError",
    "error_message": "assert 750 == 750",
    "affected_code": [
      "mortgage_underwriting/modules/lender_comparison/services.py",
      "line 95"
    ],
    "suggested_fix": "Integrate stress-tested rate into `_compute_affordability_score()` function so that all lenders are evaluated under consistent qualifying criteria per OSFI B-20.",
    "severity": "high"
  },
  {
    "title": "DOB decryption attempted in logs causing PIPEDA violation risk",
    "description": "During debugging, DOB was accidentally logged unhashed within exception handler in submission route, violating PIPEDA compliance regarding encryption-at-rest and logging restrictions.",
    "test_name": "N/A (detected via static scan)",
    "error_type": "Logging Violation",
    "stack_trace": "File \"/app/mortgage_underwriting/modules/submission/routes.py\", line 52, in submit_application\n    logger.debug(f\"Processing applicant born {applicant['dob']}\")",
    "error_message": "DOB exposed in log statement",
    "affected_code": [
      "mortgage_underwriting/modules/submission/routes.py",
      "line 52"
    ],
    "suggested_fix": "Remove or sanitize any log statements involving personal identifiers such as DOB, SIN, income, address details. Replace with correlation IDs where necessary.",
    "severity": "critical"
  },
  {
    "title": "Audit trail missing created_by field for submission records",
    "description": "New submissions do not populate `created_by` field which is mandatory per FINTRAC immutability standards. Auditability compromised due to incomplete metadata capture.",
    "test_name": "tests/integration/test_submission_integration.py::test_audit_fields_populated",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_submission_integration.py\", line 160, in test_audit_fields_populated\n    assert saved.created_by is not None\nAssertionError",
    "error_message": "assert None is not None",
    "affected_code": [
      "mortgage_underwriting/modules/submission/models.py",
      "line 28"
    ],
    "suggested_fix": "Ensure `created_by` is set from authenticated user context in service layer (`services.py`) before persisting submission model instance.",
    "severity": "medium"
  }
]
```