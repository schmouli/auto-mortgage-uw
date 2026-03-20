```json
[
  {
    "title": "Client SIN Not Encrypted Before Storage",
    "description": "The client's SIN is stored without being encrypted using AES-256 as required by PIPEDA regulations. The value appears in plain text in the database and could potentially leak into logs or error messages.",
    "test_name": "tests/unit/test_client_intake.py::test_create_client_with_valid_sin_stores_encrypted_value",
    "error_type": "AssertionError",
    "stack_trace": "tests/unit/test_client_intake.py:120: in test_create_client_with_valid_sin_stores_encrypted_value\n    assert client.sin == encrypt_pii(\"123456789\")\nE   AssertionError: assert '123456789' == '<encrypted>'",
    "error_message": "assert '123456789' == '<encrypted>'",
    "affected_code": [
      "mortgage_underwriting/modules/client_intake/models.py",
      "line 35"
    ],
    "suggested_fix": "Apply encryption via common.security.encrypt_pii before saving the SIN to the model. Ensure that decryption only occurs during authorized access and never in logs or responses.",
    "severity": "high"
  },
  {
    "title": "DOB Field Exposed in Logs During Validation Error",
    "description": "Date of birth (DOB) field is exposed in exception message when validation fails, violating PIPEDA compliance which mandates DOB must be encrypted at rest and never appear in logs or error messages.",
    "test_name": "tests/unit/test_client_intake.py::test_dob_not_logged_on_validation_error",
    "error_type": "ValueError",
    "stack_trace": "mortgage_underwriting/modules/client_intake/services.py:78: in create_client\n    raise ValueError(f\"Invalid date of birth provided: {client_data.dob}\")\nE   ValueError: Invalid date of birth provided: 2025-02-30",
    "error_message": "Invalid date of birth provided: 2025-02-30",
    "affected_code": [
      "mortgage_underwriting/modules/client_intake/services.py",
      "line 78"
    ],
    "suggested_fix": "Do not include raw DOB data in exception messages. Instead, log generic error codes and sanitize user inputs before raising exceptions.",
    "severity": "high"
  },
  {
    "title": "Client Financial Data Missing Audit Trail Fields",
    "description": "Financial transaction records lack mandatory audit fields such as created_at, updated_at, and created_by per FINTRAC regulatory requirements. This breaks immutability tracking for transactions over CAD $10,000.",
    "test_name": "tests/integration/test_client_intake_integration.py::test_client_transaction_audit_fields_present",
    "error_type": "KeyError",
    "stack_trace": "tests/integration/test_client_intake_integration.py:88: in test_client_transaction_audit_fields_present\n    assert response['created_at']\nE   KeyError: 'created_at'",
    "error_message": "KeyError: 'created_at'",
    "affected_code": [
      "mortgage_underwriting/modules/client_intake/models.py",
      "line 52"
    ],
    "suggested_fix": "Add missing audit columns (`created_at`, `updated_at`, `created_by`) to all financial transaction-related models. Apply server defaults and update triggers accordingly.",
    "severity": "high"
  },
  {
    "title": "Float Used Instead of Decimal for Income Field",
    "description": "Income field uses Python float instead of Decimal, leading to precision loss and non-compliance with project-wide financial value standards requiring use of Decimal(19,4).",
    "test_name": "tests/unit/test_client_intake.py::test_monetary_fields_use_decimal_type",
    "error_type": "TypeError",
    "stack_trace": "mortgage_underwriting/modules/client_intake/models.py:42: in <module>\n    income = Column(Float)\nE   TypeError: Financial values must use Decimal type",
    "error_message": "Financial values must use Decimal type",
    "affected_code": [
      "mortgage_underwriting/modules/client_intake/models.py",
      "line 42"
    ],
    "suggested_fix": "Replace Float column type with sqlalchemy.DECIMAL(precision=19, scale=4) for income field to ensure accurate representation of monetary amounts.",
    "severity": "high"
  },
  {
    "title": "Missing Input Validation on Client Address Fields",
    "description": "Client address fields do not enforce length limits nor reject invalid characters, allowing potential injection risks or truncation errors affecting CMHC eligibility checks.",
    "test_name": "tests/unit/test_client_intake.py::test_address_field_validation_enforced",
    "error_type": "ValidationError",
    "stack_trace": "pydantic/main.py:509: in pydantic.main.BaseModel.__init__\n    self.__pydantic_validator__.validate_python(data)\nE   pydantic_core._pydantic_core.ValidationError: 1 validation error for ClientSchema\naddress\n  String should have at most 255 characters [type=string_too_long, input_value=..., ctx=max_length=255]",
    "error_message": "String should have at most 255 characters",
    "affected_code": [
      "mortgage_underwriting/modules/client_intake/schemas.py",
      "line 28"
    ],
    "suggested_fix": "Enforce maximum string lengths and character restrictions in Pydantic schema definitions for all client personal information fields including address.",
    "severity": "medium"
  }
]
```