```json
[
  {
    "title": "Report Generation Fails for Empty Date Range",
    "description": "The reporting service raises a ValueError when start_date equals end_date due to invalid date range validation logic.",
    "test_name": "tests/unit/test_reporting.py::test_generate_report_empty_date_range",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/reporting/services.py\", line 67, in generate_monthly_summary\n    if end_date <= start_date:\n       ^^^^^^^^^^^^^^^^^^^^^^\nValueError: End date must be after start date\n",
    "error_message": "End date must be after start date",
    "affected_code": [
      "mortgage_underwriting/modules/reporting/services.py",
      "line 67"
    ],
    "suggested_fix": "Update condition to allow equal dates and adjust unit tests accordingly",
    "severity": "high"
  },
  {
    "title": "Analytics Service Returns Incorrect Total Loan Value",
    "description": "Total loan value aggregation returns incorrect sum due to improper casting of Decimal values during computation.",
    "test_name": "tests/unit/test_analytics.py::test_total_loan_value_aggregation",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/analytics/services.py\", line 34, in calculate_total_loans\n    total += loan.amount\n             ~~^^^^^^^^^^\nTypeError: unsupported operand type(s) for +=: 'decimal.Decimal' and 'float'\n",
    "error_message": "unsupported operand type(s) for +=: 'decimal.Decimal' and 'float'",
    "affected_code": [
      "mortgage_underwriting/modules/analytics/services.py",
      "line 34"
    ],
    "suggested_fix": "Ensure all monetary values are cast as Decimal before arithmetic operations",
    "severity": "high"
  },
  {
    "title": "Missing Index on Report Status Column Causes Slow Query",
    "description": "Query performance degrades significantly on large datasets due to missing index on the status column used in filtering reports.",
    "test_name": "tests/integration/test_reporting_integration.py::test_report_filter_performance",
    "error_type": "TimeoutError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/reporting/models.py\", line 22, in filter_reports_by_status\n    return session.query(Report).filter(Report.status == status)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\nsqlalchemy.exc.TimeoutError: Query exceeded timeout threshold\n",
    "error_message": "Query exceeded timeout threshold",
    "affected_code": [
      "mortgage_underwriting/modules/reporting/models.py",
      "line 22"
    ],
    "suggested_fix": "Add database index on Report.status column via new Alembic migration",
    "severity": "medium"
  },
  {
    "title": "Pagination Not Implemented in List Reports Endpoint",
    "description": "List reports endpoint does not implement pagination which leads to excessive memory usage and slow response times with large datasets.",
    "test_name": "tests/unit/test_reporting_routes.py::test_list_reports_no_pagination",
    "error_type": "NotImplementedError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/mortgage_underwriting/modules/reporting/routes.py\", line 55, in list_reports\n    raise NotImplementedError(\"Pagination is not yet implemented\")\n                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\nNotImplementedError: Pagination is not yet implemented\n",
    "error_message": "Pagination is not yet implemented",
    "affected_code": [
      "mortgage_underwriting/modules/reporting/routes.py",
      "line 55"
    ],
    "suggested_fix": "Implement query parameters skip and limit with default and maximum constraints",
    "severity": "high"
  }
]
```