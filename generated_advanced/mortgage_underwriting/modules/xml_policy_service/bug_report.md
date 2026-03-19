```json
[
  {
    "title": "XML Policy Serialization Fails for Empty Metadata Field",
    "description": "Test fails due to KeyError when serializing policy with empty metadata dictionary. The service attempts to access a key that does not exist.",
    "test_name": "tests/unit/test_xml_policy_service.py::test_serialize_empty_metadata",
    "error_type": "KeyError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_xml_policy_service.py\", line 78, in test_serialize_empty_metadata\n    result = xml_policy_service.serialize_policy(policy)\n  File \"/workspace/mortgage_underwriting/modules/xml_policy_service/services.py\", line 112, in serialize_policy\n    root.append(_build_metadata_section(policy.metadata))\n  File \"/workspace/mortgage_underwriting/modules/xml_policy_service/services.py\", line 65, in _build_metadata_section\n    version = ET.SubElement(metadata_elem, 'version')\n  File \"src/lxml/elbuilder.pxi\", line 148, in lxml.etree.SubElement\nTypeError: Argument must be bytes or unicode, got 'NoneType'",
    "error_message": "TypeError: Argument must be bytes or unicode, got 'NoneType'",
    "affected_code": [
      "modules/xml_policy_service/services.py",
      "line 65"
    ],
    "suggested_fix": "Add null check and default value handling in `_build_metadata_section()` for missing keys like 'version'. Ensure all accessed fields have fallbacks using `.get(key, '')`.",
    "severity": "high"
  },
  {
    "title": "Policy Creation Fails With Invalid Date Format in XML Input",
    "description": "Service raises ValueError when parsing date string '2026-02-30' which is an invalid calendar date but passes initial regex validation.",
    "test_name": "tests/unit/test_xml_policy_service.py::test_create_policy_invalid_date_format",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_xml_policy_service.py\", line 92, in test_create_policy_invalid_date_format\n    xml_policy_service.parse_policy_from_xml(invalid_date_xml)\n  File \"/workspace/mortgage_underwriting/modules/xml_policy_service/services.py\", line 43, in parse_policy_from_xml\n    parsed_date = datetime.fromisoformat(date_str)\nValueError: Invalid isoformat string: '2026-02-30'",
    "error_message": "Invalid isoformat string: '2026-02-30'",
    "affected_code": [
      "modules/xml_policy_service/services.py",
      "line 43"
    ],
    "suggested_fix": "Wrap datetime parsing in try-except block and raise custom InvalidDateFormat exception with user-friendly message. Add stricter pre-validation for ISO date compliance beyond regex.",
    "severity": "high"
  },
  {
    "title": "Missing Audit Fields in Policy Model During Save Operation",
    "description": "Database insert fails because created_at and updated_at fields are not populated during model instantiation in service layer.",
    "test_name": "tests/integration/test_xml_policy_integration.py::test_save_policy_with_audit_fields",
    "error_type": "IntegrityError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/integration/test_xml_policy_integration.py\", line 105, in test_save_policy_with_audit_fields\n    db.add(policy_model)\n  File \"/usr/local/lib/python3.12/site-packages/sqlalchemy/orm/session.py\", line 2690, in add\n    self._save_or_update_state(state)\nsqlalchemy.exc.IntegrityError: (psycopg2.errors.NotNullViolation) null value in column \"created_at\" violates not-null constraint",
    "error_message": "null value in column \"created_at\" violates not-null constraint",
    "affected_code": [
      "modules/xml_policy_service/models.py",
      "line 28",
      "modules/xml_policy_service/services.py",
      "line 150"
    ],
    "suggested_fix": "Ensure `created_at` defaults to `datetime.utcnow` and `updated_at` uses `onupdate=func.now()` in model definition. Alternatively, explicitly set these values in service before saving.",
    "severity": "high"
  },
  {
    "title": "Decimal Precision Loss in Monetary Amount Parsing",
    "description": "Monetary amount parsed as float instead of Decimal causing precision loss during XML ingestion. Expected Decimal('123456.78') got 123456.78000000001.",
    "test_name": "tests/unit/test_xml_policy_service.py::test_monetary_precision_loss",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_xml_policy_service.py\", line 120, in test_monetary_precision_loss\n    assert policy.amount == Decimal('123456.78')\nAssertionError: assert Decimal('123456.78000000001') == Decimal('123456.78')",
    "error_message": "assert Decimal('123456.78000000001') == Decimal('123456.78')",
    "affected_code": [
      "modules/xml_policy_service/services.py",
      "line 82"
    ],
    "suggested_fix": "Replace `float(value)` with `Decimal(str(value))` when converting XML string amounts to ensure exact decimal representation without floating point artifacts.",
    "severity": "high"
  },
  {
    "title": "PII Exposure Risk Due to Logging Raw SIN Values",
    "description": "SIN values are included directly in log statements during debug mode, violating PIPEDA encryption/storage policies even if transient.",
    "test_name": "N/A (detected via static analysis)",
    "error_type": "Security Violation",
    "stack_trace": "Detected in code review at modules/xml_policy_service/services.py:205 where raw SIN is passed into logger.debug().",
    "error_message": "Raw SIN detected in application logs exposing personal identifiers contrary to PIPEDA regulations.",
    "affected_code": [
      "modules/xml_policy_service/services.py",
      "line 205"
    ],
    "suggested_fix": "Remove direct logging of sensitive fields such as SIN. Instead log only SHA256 hash of SIN for correlation purposes. Apply encryption via `common.security.encrypt_pii()` where storage is required.",
    "severity": "critical"
  }
]
```