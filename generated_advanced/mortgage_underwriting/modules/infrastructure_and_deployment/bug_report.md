```json
[
  {
    "title": "Hardcoded configuration values detected in deployment module",
    "description": "Configuration values such as database URLs, retry limits, and timeout durations are hardcoded directly in source files instead of being sourced from environment or config.",
    "test_name": "tests/unit/test_infrastructure_config.py::test_load_db_config_from_env",
    "error_type": "AssertionError",
    "stack_trace": "tests/unit/test_infrastructure_config.py:22: in test_load_db_config_from_env\n    assert config.db_url == os.getenv('DATABASE_URL')\nE   AssertionError: assert 'postgresql://user:pass@localhost/db' == 'postgresql://env_user:env_pass@example.com/env_db'\n\nDuring handling of the above exception, another exception occurred:\nmortgage_underwriting/modules/infrastructure/services.py:15: in load_database_settings\n    self.db_url = 'postgresql://user:pass@localhost/db'",
    "error_message": "Hardcoded database URL does not match expected environment-based value",
    "affected_code": [
      "mortgage_underwriting/modules/infrastructure/services.py",
      "line 15"
    ],
    "suggested_fix": "Refactor to use pydantic settings from common/config.py; replace hardcoded strings with os.getenv() or equivalent dynamic loading mechanism",
    "severity": "high"
  },
  {
    "title": "Missing index on frequently queried email column",
    "description": "Email field used in WHERE clauses lacks an index, causing performance degradation during user lookup operations.",
    "test_name": "tests/integration/test_user_lookup_performance.py::test_email_query_response_time",
    "error_type": "TimeoutError",
    "stack_trace": "tests/integration/test_user_lookup_performance.py:34: in test_email_query_response_time\n    response = client.get(f\"/users?email={test_email}\")\ntimeout_decorator/timeout_decorator.py:82: in new_function\n    return function(*args, **kwargs)\nmortgage_underwriting/modules/users/routes.py:47: in get_user_by_email\n    user = await UserService.get_user(email=email)",
    "error_message": "Query exceeded allowed time limit of 1 second due to missing index",
    "affected_code": [
      "mortgage_underwriting/modules/users/models.py",
      "line 28"
    ],
    "suggested_fix": "Add database index using sqlalchemy Index() construct for email column in User model",
    "severity": "high"
  },
  {
    "title": "List endpoint lacks pagination support",
    "description": "Endpoint returns all records without implementing pagination controls, risking memory exhaustion and slow UI rendering.",
    "test_name": "tests/integration/test_loan_list_pagination.py::test_list_loans_no_pagination_limit",
    "error_type": "AssertionError",
    "stack_trace": "tests/integration/test_loan_list_pagination.py:19: in test_list_loans_no_pagination_limit\n    assert len(response.json()) <= 100\nE   AssertionError: assert 5432 <= 100",
    "error_message": "Response contains more than maximum allowed items per page (100)",
    "affected_code": [
      "mortgage_underwriting/modules/loans/routes.py",
      "line 31"
    ],
    "suggested_fix": "Implement skip/limit parameters with default and max bounds; update route signature and service method accordingly",
    "severity": "high"
  },
  {
    "title": "Potential SQL injection vulnerability via raw string formatting",
    "description": "Raw string concatenation is used in constructing SQL queries which may expose application to SQL injection attacks.",
    "test_name": "tests/unit/test_sql_injection_check.py::test_unsafe_query_building",
    "error_type": "SecurityWarning",
    "stack_trace": "mortgage_underwriting/modules/reports/services.py:67: in build_custom_report_query\n    query = f'SELECT * FROM loans WHERE status = {status}'\nE   sql_injection_detector.Warning: Possible unsafe query building pattern detected",
    "error_message": "Detected potential SQL injection vector through direct string interpolation in query construction",
    "affected_code": [
      "mortgage_underwriting/modules/reports/services.py",
      "line 67"
    ],
    "suggested_fix": "Replace raw string formatting with SQLAlchemy's built-in parameter binding methods like session.execute(text(...), {'param': val})",
    "severity": "high"
  },
  {
    "title": "Foreign key constraint missing explicit ondelete behavior",
    "description": "Foreign key relationships do not define what happens upon referenced row deletion, potentially leading to orphaned data or integrity errors.",
    "test_name": "tests/unit/test_model_relationships.py::test_fk_ondelete_behavior_defined",
    "error_type": "IntegrityError",
    "stack_trace": "sqlalchemy.exc.IntegrityError: (psycopg2.errors.ForeignKeyViolation) update or delete on table \"borrowers\" violates foreign key constraint \"fk_loans_borrower_id\"\nDETAIL:  Key (id)=(123) is still referenced from table \"loans\".\n",
    "error_message": "Foreign key relationship has no defined cascade/delete behavior",
    "affected_code": [
      "mortgage_underwriting/modules/loans/models.py",
      "line 22"
    ],
    "suggested_fix": "Explicitly set ondelete='CASCADE' or appropriate referential action when defining ForeignKey constraints",
    "severity": "high"
  }
]
```