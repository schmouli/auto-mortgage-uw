```json
[
  {
    "title": "Report Generation Fails for Empty Date Range",
    "description": "The reporting service raises a ValueError when start_date is after end_date, but does not gracefully handle empty date ranges which leads to uncaught exceptions in edge cases.",
    "test_name": "tests/unit/test_reporting.py::test_generate_report_empty_date_range",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_reporting.py\", line 112, in test_generate_report_empty_date_range\n    await reporting_service.generate_monthly_summary(start_date='2026-02-01', end_date='2026-01-31')\n  File \"/app/mortgage_underwriting/modules/reporting/services.py\", line 78, in generate_monthly_summary\n    raise ValueError(\"Start date must be before end date\")\nValueError: Start date must be before end date",
    "error_message": "Start date must be before end date",
    "affected_code": [
      "mortgage_underwriting/modules/reporting/services.py",
      "line 78"
    ],
    "suggested_fix": "Add validation to check if the date range is valid and return an empty result set instead of raising an exception.",
    "severity": "medium"
  },
  {
    "title": "Decimal Precision Loss in Financial Totals",
    "description": "Financial totals in generated reports lose precision due to improper rounding during aggregation, violating regulatory requirements for accurate financial computations.",
    "test_name": "tests/unit/test_reporting.py::test_decimal_precision_in_totals",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_reporting.py\", line 65, in test_decimal_precision_in_totals\n    assert total == Decimal('123456.7891')\nAssertionError: assert Decimal('123456.79') == Decimal('123456.7891')",
    "error_message": "assert Decimal('123456.79') == Decimal('123456.7891')",
    "affected_code": [
      "mortgage_underwriting/modules/reporting/services.py",
      "line 45"
    ],
    "suggested_fix": "Ensure all financial aggregations use Decimal with appropriate quantization to prevent precision loss.",
    "severity": "high"
  },
  {
    "title": "Missing Audit Fields in Report Models",
    "description": "Report models do not include required audit fields such as created_at and updated_at, violating mandatory compliance standards.",
    "test_name": "tests/unit/test_reporting.py::test_audit_fields_present",
    "error_type": "AttributeError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_reporting.py\", line 30, in test_audit_fields_present\n    getattr(ReportModel, 'updated_at')\nAttributeError: type object 'ReportModel' has no attribute 'updated_at'",
    "error_message": "type object 'ReportModel' has no attribute 'updated_at'",
    "affected_code": [
      "mortgage_underwriting/modules/reporting/models.py",
      "line 22"
    ],
    "suggested_fix": "Update ReportModel to include created_at and updated_at fields with proper SQLAlchemy column definitions.",
    "severity": "high"
  },
  {
    "title": "PII Exposure in Structured Logs",
    "description": "During report generation, borrower SIN numbers were exposed in structured logs, violating PIPEDA encryption and logging policies.",
    "test_name": "tests/integration/test_reporting_integration.py::test_no_pii_in_logs",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_reporting_integration.py\", line 88, in test_no_pii_in_logs\n    assert 'sin' not in log_output\nAssertionError",
    "error_message": "assert 'sin' not in log_output",
    "affected_code": [
      "mortgage_underwriting/modules/reporting/services.py",
      "line 105"
    ],
    "suggested_fix": "Sanitize log statements by removing or hashing sensitive data like SIN before logging; ensure all PII fields are encrypted at rest per security policy.",
    "severity": "critical"
  }
]
```