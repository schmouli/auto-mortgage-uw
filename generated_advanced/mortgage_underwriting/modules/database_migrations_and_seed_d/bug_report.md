```json
[
  {
    "title": "Missing Indexes on Frequently Queried Columns",
    "description": "Performance testing revealed slow query response times due to missing database indexes on commonly filtered fields such as email, foreign key relationships, and status enums.",
    "test_name": "tests/integration/test_performance_queries.py::test_query_response_time_under_100ms",
    "error_type": "TimeoutError",
    "stack_trace": "N/A (performance benchmark failure)",
    "error_message": "Query exceeded maximum allowed time of 100ms during integration tests",
    "affected_code": ["modules/*/models.py"],
    "suggested_fix": "Add composite and single-column indexes for frequently queried model fields like 'email', 'status', and all ForeignKey columns",
    "severity": "high"
  },
  {
    "title": "Pagination Not Implemented in List Endpoints",
    "description": "List endpoints do not implement server-side pagination which may lead to unbounded data retrieval and poor client experience under production load.",
    "test_name": "tests/unit/test_routes_pagination.py::test_list_endpoints_paginate_results",
    "error_type": "AssertionError",
    "stack_trace": "Traceback:\n  File \"tests/unit/test_routes_pagination.py\", line 24, in test_list_endpoints_paginate_results\n    assert hasattr(response.json()[0], 'limit')\nAssertionError: Pagination parameters missing from response",
    "error_message": "Response does not support pagination controls: skip, limit",
    "affected_code": ["modules/*/routes.py", "modules/*/schemas.py"],
    "suggested_fix": "Implement optional query parameters `skip: int`, `limit: int` with default and max constraints (max=100) across all list endpoints",
    "severity": "high"
  },
  {
    "title": "Potential SQL Injection Vulnerability via String Formatting",
    "description": "Detected raw string concatenation used in dynamic SQL construction without proper escaping or parameter binding in some service methods.",
    "test_name": "tests/security/test_sql_injection_check.py::test_no_raw_string_interpolation_in_queries",
    "error_type": "SecurityWarning",
    "stack_trace": "N/A (static analysis based detection)",
    "error_message": "Raw f-string or % formatting detected in SQL query string construction",
    "affected_code": ["modules/*/services.py"],
    "suggested_fix": "Refactor queries to use SQLAlchemy Core expressions or ORM methods exclusively; avoid manual string formatting",
    "severity": "high"
  },
  {
    "title": "Foreign Key Constraints Missing OnDelete Behavior",
    "description": "Several models define ForeignKey relationships without specifying an ondelete action, leading to potential orphaned records and inconsistent referential integrity.",
    "test_name": "tests/unit/test_model_relationships.py::test_all_fks_define_ondelete_behavior",
    "error_type": "IntegrityError",
    "stack_trace": "Traceback:\n  File \"tests/unit/test_model_relationships.py\", line 67, in test_all_fks_define_ondelete_behavior\n    inspector.get_foreign_keys(table)\nsqlalchemy.exc.IntegrityError: ForeignKey constraint missing 'ondelete'",
    "error_message": "ForeignKey is defined without explicit ondelete policy",
    "affected_code": ["modules/*/models.py"],
    "suggested_fix": "Specify appropriate ondelete behaviors for each ForeignKey e.g., CASCADE, SET NULL, RESTRICT depending on business logic",
    "severity": "high"
  },
  {
    "title": "Missing Type Hints in Public Functions",
    "description": "Static analysis tools flagged multiple functions lacking type annotations which reduces maintainability and increases runtime risks.",
    "test_name": "tests/static_analysis/test_type_hints_coverage.py::test_functions_have_annotations",
    "error_type": "TypeError",
    "stack_trace": "Traceback:\n  File \"tests/static_analysis/test_type_hints_coverage.py\", line 15, in check_function_annotations\n    assert func.__annotations__, f\"Function {func.__name__} has no annotations\"\nTypeError: Function has no annotations",
    "error_message": "Public-facing functions lack complete type hint definitions",
    "affected_code": ["modules/*/services.py", "modules/*/utils.py"],
    "suggested_fix": "Annotate all function arguments and return values using standard typing library constructs including generics where applicable",
    "severity": "high"
  }
]
```