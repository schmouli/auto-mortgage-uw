```json
[
  {
    "title": "Condition evaluation fails for null property values",
    "description": "Test failure occurs when evaluating underwriting conditions with null property values. The service raises a TypeError due to improper handling of None values during logical comparisons.",
    "test_name": "tests/unit/test_conditions_service.py::test_evaluate_condition_with_null_property",
    "error_type": "TypeError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/conditions/services.py\", line 78, in evaluate_condition\n    result = eval(expression)\n             ^^^^^^^^^^^^^^^^\n  File \"<string>\", line 1, in <module>\nTypeError: '>' not supported between instances of 'NoneType' and 'Decimal'",
    "error_message": "TypeError: '>' not supported between instances of 'NoneType' and 'Decimal'",
    "affected_code": [
      "mortgage_underwriting/modules/conditions/services.py",
      "line 78"
    ],
    "suggested_fix": "Add explicit null-check validation before evaluating condition expressions. Replace direct eval() usage with safer parsing or validated expression engine.",
    "severity": "high"
  },
  {
    "title": "Messaging service sends unencrypted PII in logs",
    "description": "During message creation, borrower SIN is logged in plaintext violating PIPEDA compliance. Encryption method missing from messaging flow despite being available in common/security.py.",
    "test_name": "tests/integration/test_messaging_integration.py::test_create_secure_borrower_message",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/messaging/services.py\", line 32, in log_message_event\n    logger.info(f\"Message sent for borrower {borrower.sin}\")\n  File \"/app/mortgage_underwriting/common/logging.py\", line 15, in info\n    raise ValueError(\"PII detected in log statement\")\nValueError: PII detected in log statement",
    "error_message": "ValueError: PII detected in log statement",
    "affected_code": [
      "mortgage_underwriting/modules/messaging/services.py",
      "line 32"
    ],
    "suggested_fix": "Replace borrower.sin with borrower.sin_hash or remove PII entirely from log statements. Ensure all log calls are reviewed for PII leakage.",
    "severity": "high"
  },
  {
    "title": "Conditions engine does not enforce FINTRAC audit trail immutability",
    "description": "Audit fields such as created_at are modifiable after insertion which violates FINTRAC’s immutable audit trail requirement.",
    "test_name": "tests/unit/test_conditions_models.py::test_condition_audit_fields_immutability",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_conditions_models.py\", line 64, in test_condition_audit_fields_immutability\n    assert condition.created_at == original_created_at\nAssertionError: assert datetime.datetime(2026, 3, 1, 12, 0, tzinfo=datetime.timezone.utc) == datetime.datetime(2026, 3, 1, 11, 59, tzinfo=datetime.timezone.utc)",
    "error_message": "AssertionError: assert datetime.datetime(2026, 3, 1, 12, 0, tzinfo=datetime.timezone.utc) == datetime.datetime(2026, 3, 1, 11, 59, tzinfo=datetime.timezone.utc)",
    "affected_code": [
      "mortgage_underwriting/modules/conditions/models.py",
      "line 22"
    ],
    "suggested_fix": "Remove server_default=func.now() from updated_at column definition and replace with onupdate=None or implement custom setter that prevents modification of created_at/updated_at once set.",
    "severity": "high"
  },
  {
    "title": "Messaging schema allows float instead of Decimal for transaction_amount",
    "description": "Pydantic schema for messaging uses float type for transaction_amount which violates regulatory requirement to always use Decimal for financial values.",
    "test_name": "tests/unit/test_messaging_schemas.py::test_transaction_amount_is_decimal",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_messaging_schemas.py\", line 29, in test_transaction_amount_is_decimal\n    assert isinstance(msg.transaction_amount, Decimal)\nAssertionError: assert False",
    "error_message": "AssertionError: assert False",
    "affected_code": [
      "mortgage_underwriting/modules/messaging/schemas.py",
      "line 18"
    ],
    "suggested_fix": "Change type hint and validator in MessagingSchema.transaction_amount from float to Decimal. Also ensure serialization handles Decimals correctly using json_encoders.",
    "severity": "high"
  }
]
```