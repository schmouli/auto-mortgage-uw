```json
[{
  "title": "GDS Calculation fails for negative gross income",
  "description": "The GDS calculation service raises a ValueError when provided with negative gross income, which is not handled gracefully. This violates OSFI B-20 expectation that all ratio calculations must be auditable and handle edge cases.",
  "test_name": "tests/unit/test_underwriting_engine.py::test_gds_with_negative_gross_income",
  "error_type": "ValueError",
  "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_underwriting_engine.py\", line 120, in test_gds_with_negative_gross_income\n    result = await calculate_gds(applicant_profile)\n  File \"/app/mortgage_underwriting/modules/underwriting_engine/services.py\", line 47, in calculate_gds\n    if total_annual_housing_costs < 0:\nValueError: Financial values cannot be negative",
  "error_message": "Financial values cannot be negative",
  "affected_code": [
    "mortgage_underwriting/modules/underwriting_engine/services.py",
    "line 47"
  ],
  "suggested_fix": "Add input validation at start of calculate_gds() to reject negative gross incomes with structured error response",
  "severity": "high"
},
{
  "title": "TDS stress test uses incorrect rate logic",
  "description": "Under OSFI B-20, the qualifying rate should be max(contract_rate + 2%, 5.25%), but current implementation defaults to contract_rate + 2% without checking minimum threshold.",
  "test_name": "tests/integration/test_underwriting_integration.py::test_tds_stress_test_minimum_rate_enforced",
  "error_type": "AssertionError",
  "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_underwriting_integration.py\", line 89, in test_tds_stress_test_minimum_rate_enforced\n    assert calculated_rate >= Decimal('5.25')\nAssertionError",
  "error_message": "assert Decimal('4.50') >= Decimal('5.25')",
  "affected_code": [
    "mortgage_underwriting/modules/underwriting_engine/services.py",
    "line 103"
  ],
  "suggested_fix": "Update _apply_osfi_stress_test() method to enforce: qualifying_rate = max(contract_rate + 2%, 5.25%)",
  "severity": "high"
},
{
  "title": "LTV-based insurance premium lookup returns wrong tier",
  "description": "CMHC compliance requires precise LTV thresholds for insurance premiums. Current logic misclassifies applicants near boundary (e.g., LTV=85.00% assigned 3.10% instead of 2.80%).",
  "test_name": "tests/unit/test_underwriting_engine.py::test_insurance_premium_boundary_ltv_85_percent",
  "error_type": "AssertionError",
  "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_underwriting_engine.py\", line 210, in test_insurance_premium_boundary_ltv_85_percent\n    assert premium == Decimal('2.80')\nAssertionError",
  "error_message": "assert Decimal('3.10') == Decimal('2.80')",
  "affected_code": [
    "mortgage_underwriting/modules/underwriting_engine/services.py",
    "line 156"
  ],
  "suggested_fix": "Refactor _lookup_cmhc_premium() to use strict inequality checks per CMHC tiers: <=85% = 2.80%, <=90% = 3.10%",
  "severity": "high"
},
{
  "title": "DOB decryption attempted on None value",
  "description": "PIPEDA mandates encryption of DOB fields. Service attempts decryption even when DOB is null, causing AttributeError during applicant retrieval.",
  "test_name": "tests/unit/test_underwriting_engine.py::test_retrieve_applicant_with_null_dob",
  "error_type": "AttributeError",
  "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_underwriting_engine.py\", line 67, in test_retrieve_applicant_with_null_dob\n    applicant = await get_applicant(session, applicant_id)\n  File \"/app/mortgage_underwriting/modules/underwriting_engine/services.py\", line 205, in get_applicant\n    decrypted_dob = decrypt_pii(encrypted_dob)\n  File \"/app/mortgage_underwriting/common/security.py\", line 32, in decrypt_pii\n    return cipher.decrypt(data).decode()\nAttributeError: 'NoneType' object has no attribute 'decode'",
  "error_message": "'NoneType' object has no attribute 'decode'",
  "affected_code": [
    "mortgage_underwriting/modules/underwriting_engine/services.py",
    "line 205"
  ],
  "suggested_fix": "Check for None before attempting decryption in get_applicant(); return None safely",
  "severity": "medium"
}]
```