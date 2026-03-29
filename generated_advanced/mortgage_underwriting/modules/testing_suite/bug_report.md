```json
[
  {
    "title": "GDS Calculation fails for negative values",
    "description": "The GDS calculation service raises a ValueError when provided with negative gross income, which is not handled gracefully. Expected behavior is to return Decimal('0.00').",
    "test_name": "tests/unit/test_gds_calculator.py::test_negative_gross_income",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_gds_calculator.py\", line 45, in test_negative_gross_income\n    result = calculate_gds(...)\n  File \"mortgage_underwriting/modules/underwriting_engine/services.py\", line 72, in calculate_gds\n    raise ValueError(\"Invalid input: Negative gross income not allowed\")\nValueError: Invalid input: Negative gross income not allowed",
    "error_message": "Invalid input: Negative gross income not allowed",
    "affected_code": [
      "mortgage_underwriting/modules/underwriting_engine/services.py",
      "line 72"
    ],
    "suggested_fix": "Add validation at the start of calculate_gds() to return Decimal('0.00') if gross_income is negative.",
    "severity": "high"
  },
  {
    "title": "Missing encryption for SIN field in borrower model",
    "description": "Borrower SIN field stored without encryption despite PIPEDA compliance requirement. Field should be encrypted using AES-256 and never logged or returned in API responses.",
    "test_name": "tests/integration/test_borrower_integration.py::test_sin_encryption",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/integration/test_borrower_integration.py\", line 31, in test_sin_encryption\n    assert borrower.sin.startswith('enc:')\nAssertionError",
    "error_message": "assert '' == 'enc:'",
    "affected_code": [
      "mortgage_underwriting/modules/borrower/models.py",
      "line 28"
    ],
    "suggested_fix": "Implement encryption in borrower model using common/security.py.encrypt_pii(). Ensure all read/write operations encrypt/decrypt appropriately.",
    "severity": "critical"
  },
  {
    "title": "LTV calculation returns incorrect decimal precision",
    "description": "Loan-to-value ratio computation loses precision due to float-based intermediate step. Expected Decimal('0.85'), got Decimal('0.8499999999999999').",
    "test_name": "tests/unit/test_ltv_calculator.py::test_precision_handling",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_ltv_calculator.py\", line 22, in test_precision_handling\n    assert ltv == Decimal('0.85')\nAssertionError",
    "error_message": "assert Decimal('0.8499999999999999') == Decimal('0.85')",
    "affected_code": [
      "mortgage_underwriting/modules/mortgage_calculations/services.py",
      "line 15"
    ],
    "suggested_fix": "Ensure all numeric literals and computations use Decimal exclusively. Replace any implicit float conversion.",
    "severity": "high"
  },
  {
    "title": "Insurance premium lookup fails above 95% LTV",
    "description": "CMHC insurance premium lookup throws KeyError for LTV ratios exceeding 95%, even though such loans may exist in practice and require special handling per policy.",
    "test_name": "tests/unit/test_insurance_premium.py::test_premium_lookup_over_95_percent",
    "error_type": "KeyError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_insurance_premium.py\", line 37, in test_premium_lookup_over_95_percent\n    premium = get_insurance_premium(ltv=Decimal('0.96'))\n  File \"mortgage_underwriting/modules/cmhc_compliance/services.py\", line 55, in get_insurance_premium\n    return PREMIUM_TIERS[lv_bucket]\nKeyError: '>95%'",
    "error_message": "'KeyError: \\'\\\\'>95%\\'\\''",
    "affected_code": [
      "mortgage_underwriting/modules/cmhc_compliance/services.py",
      "line 55"
    ],
    "suggested_fix": "Update premium tier mapping to explicitly handle edge cases like '>95%' and define appropriate business logic or rejection criteria.",
    "severity": "medium"
  },
  {
    "title": "Audit trail missing on financial transaction creation",
    "description": "FINTRAC audit trail requirement violated: Financial transactions lack created_at and created_by fields upon insertion into DB.",
    "test_name": "tests/integration/test_transaction_audit.py::test_audit_fields_present",
    "error_type": "AttributeError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/integration/test_transaction_audit.py\", line 29, in test_audit_fields_present\n    assert hasattr(transaction, 'created_at')\nAttributeError: 'Transaction' object has no attribute 'created_at'",
    "error_message": "'Transaction' object has no attribute 'created_at'",
    "affected_code": [
      "mortgage_underwriting/modules/financial_transactions/models.py",
      "line 18"
    ],
    "suggested_fix": "Add created_at (DateTime, default=datetime.utcnow), created_by (String), updated_at (DateTime, default=datetime.utcnow) to Transaction model definition.",
    "severity": "high"
  }
]
```