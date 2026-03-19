```json
[
  {
    "title": "Missing Audit Fields in Financial Transaction Model",
    "description": "The financial_transaction table is missing required audit fields: created_at, updated_at. This violates FINTRAC compliance which mandates immutable audit trails with 5-year retention.",
    "test_name": "tests/unit/test_fintrac_compliance.py::test_audit_fields_present",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_fintrac_compliance.py\", line 23, in test_audit_fields_present\n    assert hasattr(FinancialTransaction, 'created_at')\nAssertionError",
    "error_message": "assert hasattr(FinancialTransaction, 'created_at')",
    "affected_code": ["modules/fintrac/models.py", "line 15"],
    "suggested_fix": "Add created_at and updated_at columns with DateTime(timezone=True), default=func.now(), onupdate=func.now() to FinancialTransaction model",
    "severity": "high"
  },
  {
    "title": "Large Transaction Not Flagged",
    "description": "Transactions exceeding CAD $10,000 are not flagged with explicit transaction type as required by FINTRAC. The service layer fails to set requires_reporting flag.",
    "test_name": "tests/unit/test_fintrac_compliance.py::test_large_transactions_flagged",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_fintrac_compliance.py\", line 41, in test_large_transactions_flagged\n    assert result.requires_reporting is True\nAssertionError",
    "error_message": "assert False is True",
    "affected_code": ["modules/fintrac/services.py", "line 32"],
    "suggested_fix": "Implement threshold check in create_transaction method: if amount > 10000: transaction.requires_reporting = True",
    "severity": "high"
  },
  {
    "title": "PII Data Written to Logs",
    "description": "Customer DOB and partial SIN were found in application logs during transaction processing, violating PIPEDA privacy requirements and FINTRAC data protection standards.",
    "test_name": "tests/integration/test_fintrac_integration.py::test_no_pii_in_logs",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/integration/test_fintrac_integration.py\", line 58, in test_no_pii_in_logs\n    assert 'dob' not in log_output\nAssertionError",
    "error_message": "assert 'dob' not in log_output",
    "affected_code": ["modules/fintrac/services.py", "line 67", "common/security.py", "line 12"],
    "suggested_fix": "Remove logging of customer object; ensure DOB/SIN use encrypted storage via encrypt_pii(); add scrubbing filters to structlog configuration",
    "severity": "high"
  }
]
```