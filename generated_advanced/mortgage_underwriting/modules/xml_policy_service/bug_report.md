```json
[
  {
    "title": "XML Policy Generation Fails on Missing Required Field",
    "description": "Test failure due to KeyError when generating XML policy document because 'loan_amount' is missing from input payload.",
    "test_name": "tests/unit/test_xml_policy_service.py::test_generate_policy_missing_loan_amount",
    "error_type": "KeyError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_xml_policy_service.py\", line 42, in test_generate_policy_missing_loan_amount\n    await xml_policy_service.generate_policy(data)\n  File \"/workspace/mortgage_underwriting/modules/xml_policy_service/services.py\", line 28, in generate_policy\n    loan_amount = data['loan_amount']\nKeyError: 'loan_amount'",
    "error_message": "'loan_amount'",
    "affected_code": [
      "modules/xml_policy_service/services.py",
      "line 28"
    ],
    "suggested_fix": "Add validation at start of generate_policy() to check required fields using Pydantic schema or manual checks. Return structured error response if validation fails.",
    "severity": "high"
  },
  {
    "title": "XML Policy Schema Validation Not Enforced Before Processing",
    "description": "Service does not validate incoming request against defined Pydantic schema before accessing nested attributes, leading to AttributeError.",
    "test_name": "tests/unit/test_xml_policy_service.py::test_invalid_property_type_raises_error",
    "error_type": "AttributeError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_xml_policy_service.py\", line 71, in test_invalid_property_type_raises_error\n    await xml_policy_service.generate_policy(invalid_data)\n  File \"/workspace/mortgage_underwriting/modules/xml_policy_service/services.py\", line 35, in generate_policy\n    property_value = data.property_details.value\nAttributeError: 'dict' object has no attribute 'property_details'",
    "error_message": "'dict' object has no attribute 'property_details'",
    "affected_code": [
      "modules/xml_policy_service/services.py",
      "line 35"
    ],
    "suggested_fix": "Deserialize raw dict into Pydantic model (e.g., PolicyRequestSchema) before processing. This ensures type safety and early error detection.",
    "severity": "high"
  },
  {
    "title": "Decimal Conversion Error in Financial Fields",
    "description": "Attempting to convert string value 'N/A' to Decimal raises InvalidOperation error during XML generation step.",
    "test_name": "tests/unit/test_xml_policy_service.py::test_decimal_conversion_fails_with_invalid_input",
    "error_type": "InvalidOperation",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_xml_policy_service.py\", line 98, in test_decimal_conversion_fails_with_invalid_input\n    await xml_policy_service.generate_policy(bad_financial_data)\n  File \"/workspace/mortgage_underwriting/modules/xml_policy_service/services.py\", line 50, in generate_policy\n    total_debt = sum(Decimal(d) for d in debts)\n  File \"/workspace/mortgage_underwriting/modules/xml_policy_service/services.py\", line 50, in <genexpr>\n    total_debt = sum(Decimal(d) for d in debts)\ndecimal.InvalidOperation: [<class 'decimal.ConversionSyntax'>]",
    "error_message": "[<class 'decimal.ConversionSyntax'>]",
    "affected_code": [
      "modules/xml_policy_service/services.py",
      "line 50"
    ],
    "suggested_fix": "Wrap all Decimal conversions in try-except blocks or pre-validate input strings with regex pattern matching for numeric formats. Raise custom exception with user-friendly message.",
    "severity": "medium"
  },
  {
    "title": "Missing Audit Fields Cause Integrity Constraint Violation",
    "description": "Database insert fails due to missing created_at and updated_at values which are mandatory per regulatory audit trail rules.",
    "test_name": "tests/integration/test_xml_policy_integration.py::test_save_policy_creates_audit_fields",
    "error_type": "IntegrityError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/integration/test_xml_policy_integration.py\", line 115, in test_save_policy_creates_audit_fields\n    await xml_policy_service.save_policy(policy_model)\n  File \"/workspace/mortgage_underwriting/modules/xml_policy_service/services.py\", line 120, in save_policy\n    session.add(policy_model)\n  File \"/usr/local/lib/python3.12/site-packages/sqlalchemy/orm/session.py\", line 2698, in add\n    self._save_or_update_state(state)\nsqlalchemy.exc.IntegrityError: (psycopg2.errors.NotNullViolation) null value in column \"created_at\" violates not-null constraint",
    "error_message": "(psycopg2.errors.NotNullViolation) null value in column \"created_at\" violates not-null constraint",
    "affected_code": [
      "modules/xml_policy_service/models.py",
      "line 67"
    ],
    "suggested_fix": "Set server_default=func.now() on created_at column and use default=datetime.utcnow on updated_at. Alternatively set these values explicitly in service layer before saving.",
    "severity": "high"
  }
]
```