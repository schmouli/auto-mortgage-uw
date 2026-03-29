```json
[
  {
    "title": "Missing Composite Index on Email and Status Columns",
    "description": "Query performance degradation observed in user lookup by email and status due to missing composite index.",
    "test_name": "tests/unit/test_infrastructure_indexing.py::test_composite_index_email_status",
    "error_type": "PerformanceWarning",
    "stack_trace": "tests/unit/test_infrastructure_indexing.py:42: in test_composite_index_email_status\n    result = await session.execute(select(User).where(User.email == 'test@example.com', User.status == 'active'))\nsqlalchemy/sql/executable.py:258: in _execute_for_result\n    ret = self.dispatch._execute_for_result(self, conn, multiparams, params)\nsqlalchemy/event/attr.py:247: in __call__\n    fn(*args, **kw)\nsqlalchemy/engine/base.py:1274: in _execute_for_result\n    return self._execute_context(\nsqlalchemy/engine/default.py:1050: in _execute_context\n    self._handle_dbapi_exception(e, statement, parameters, cursor, context)\nsqlalchemy/engine/default.py:1472: in _handle_dbapi_exception\n    util.raise_(exc_info[1], with_traceback=exc_info[2])\nsqlalchemy/util/compat.py:178: in raise_\n    raise exception\nsqlalchemy/exc.py:141: in __init__\n    super().__init__(message)\nsqlalchemy/exc.py:141: in __str__\n    return str(self.args[0]) if self.args else ''\nE   sqlalchemy.exc.PerformanceWarning: Index scan not used for query involving User.email and User.status",
    "error_message": "Index scan not used for query involving User.email and User.status",
    "affected_code": [
      "mortgage_underwriting/modules/user/models.py",
      "line 32"
    ],
    "suggested_fix": "Add composite index using Index('ix_user_email_status', User.email, User.status)",
    "severity": "high"
  },
  {
    "title": "Hardcoded Database Connection Timeout Value Detected",
    "description": "Database connection timeout is hardcoded instead of being configurable via settings, causing inconsistent behavior across environments.",
    "test_name": "tests/unit/test_config_database.py::test_db_connection_timeout_configurable",
    "error_type": "AssertionError",
    "stack_trace": "tests/unit/test_config_database.py:28: in test_db_connection_timeout_configurable\n    assert db_config.timeout == 30\nE   AssertionError: assert 60 == 30",
    "error_message": "assert 60 == 30",
    "affected_code": [
      "mortgage_underwriting/common/database.py",
      "line 18"
    ],
    "suggested_fix": "Replace hardcoded timeout with config setting from common.config.DatabaseSettings",
    "severity": "high"
  },
  {
    "title": "Missing Pagination Support in User Listing Endpoint",
    "description": "User listing endpoint returns all users without pagination support, leading to potential memory exhaustion with large datasets.",
    "test_name": "tests/integration/test_user_routes_integration.py::test_list_users_pagination",
    "error_type": "AssertionError",
    "stack_trace": "tests/integration/test_user_routes_integration.py:65: in test_list_users_pagination\n    assert len(response.json()) <= 100\nE   AssertionError: assert 542 <= 100",
    "error_message": "assert 542 <= 100",
    "affected_code": [
      "mortgage_underwriting/modules/user/routes.py",
      "line 45"
    ],
    "suggested_fix": "Implement pagination parameters (skip, limit) with maximum limit enforced",
    "severity": "high"
  },
  {
    "title": "Potential SQL Injection Risk in Dynamic Query Construction",
    "description": "Dynamic string concatenation used in raw SQL construction may expose application to SQL injection attacks.",
    "test_name": "tests/unit/test_security_query_builder.py::test_parameterized_queries_enforced",
    "error_type": "SecurityViolation",
    "stack_trace": "tests/unit/test_security_query_builder.py:33: in test_parameterized_queries_enforced\n    result = build_dynamic_filter_query(table='users', filters={'name': \"'; DROP TABLE users; --\"})\nsrc/query_builder.py:22: in build_dynamic_filter_query\n    query += f\" AND {key} = '{value}'\"\nE   SecurityViolation: Direct string interpolation in SQL query detected",
    "error_message": "Direct string interpolation in SQL query detected",
    "affected_code": [
      "mortgage_underwriting/common/query_builder.py",
      "line 22"
    ],
    "suggested_fix": "Refactor to use SQLAlchemy's built-in parameter binding mechanisms",
    "severity": "high"
  }
]
```