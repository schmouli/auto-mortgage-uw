```json
[
  {
    "title": "Missing Indexes on Frequently Queried Columns",
    "description": "Detected missing database indexes on commonly filtered/query columns such as email, status fields, and foreign key relationships. This can lead to performance degradation under load.",
    "test_name": "tests/integration/test_admin_performance.py::test_user_list_endpoint_speed",
    "error_type": "TimeoutError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/integration/test_admin_performance.py\", line 32, in test_user_list_endpoint_speed\n    response = client.get('/api/v1/admin/users?status=active')\n  File \"httpx/_client.py\", line 1234, in get\n    return self.request(...)\n  File \"httpx/_client.py\", line 1111, in request\n    raise TimeoutException(\"Request timed out after 5s\")\nhttpx.TimeoutException: Request timed out after 5s",
    "error_message": "Request timed out after 5s",
    "affected_code": [
      "mortgage_underwriting/modules/admin/models.py",
      "line 42"
    ],
    "suggested_fix": "Add indexes to frequently queried model fields like `email`, `status`, and all foreign keys using `index=True` in SQLAlchemy column definitions.",
    "severity": "high"
  },
  {
    "title": "List Endpoints Lack Pagination Support",
    "description": "Admin panel list endpoints do not implement pagination which may result in excessive memory usage or timeouts when querying large datasets.",
    "test_name": "tests/unit/test_admin_routes.py::test_list_users_no_pagination",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_admin_routes.py\", line 78, in test_list_users_no_pagination\n    assert len(response.json()) <= 100\nAssertionError: assert 1000 <= 100",
    "error_message": "assert 1000 <= 100",
    "affected_code": [
      "mortgage_underwriting/modules/admin/routes.py",
      "line 65"
    ],
    "suggested_fix": "Implement query parameters `skip` and `limit` with enforced maximum limit of 100 records per page. Update service layer to support slicing.",
    "severity": "high"
  },
  {
    "title": "Potential SQL Injection Vulnerability in Raw Queries",
    "description": "Raw SQL queries detected without proper parameter binding, exposing application to potential SQL injection risks.",
    "test_name": "tests/unit/test_admin_services.py::test_search_users_sql_injection_risk",
    "error_type": "SecurityWarning",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_admin_services.py\", line 112, in test_search_users_sql_injection_risk\n    result = await search_users(\"'; DROP TABLE users; --\")\n  File \"mortgage_underwriting/modules/admin/services.py\", line 89, in search_users\n    result = await session.execute(text(query))\nsqlalchemy.exc.ProgrammingError: (psycopg2.ProgrammingError) syntax error at or near \"DROP\"",
    "error_message": "(psycopg2.ProgrammingError) syntax error at or near \"DROP\"",
    "affected_code": [
      "mortgage_underwriting/modules/admin/services.py",
      "line 85"
    ],
    "suggested_fix": "Refactor raw SQL execution to use SQLAlchemy's built-in parameterized queries via `.execute(text(sql), {'param': value})` to prevent injection.",
    "severity": "high"
  },
  {
    "title": "Foreign Key Constraints Missing OnDelete Behavior",
    "description": "Several ForeignKey definitions lack explicit `ondelete` clauses, leading to inconsistent cascading behavior during deletions.",
    "test_name": "tests/unit/test_admin_models.py::test_foreign_key_ondelete_behavior",
    "error_type": "IntegrityError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_admin_models.py\", line 45, in test_foreign_key_ondelete_behavior\n    await session.delete(parent_obj)\n  File \"sqlalchemy/ext/asyncio/session.py\", line 200, in delete\n    return self.sync_session.delete(instance)\nsqlalchemy.exc.IntegrityError: (psycopg2.errors.ForeignKeyViolation) update or delete violates foreign key constraint",
    "error_message": "(psycopg2.errors.ForeignKeyViolation) update or delete violates foreign key constraint",
    "affected_code": [
      "mortgage_underwriting/modules/admin/models.py",
      "line 30"
    ],
    "suggested_fix": "Explicitly define `ondelete='CASCADE'` or appropriate action for each ForeignKey relationship in models.py.",
    "severity": "high"
  },
  {
    "title": "Missing Type Hints in Public Functions",
    "description": "Multiple public-facing functions in admin services and routes are missing type hints, reducing code maintainability and static analysis capabilities.",
    "test_name": "tests/unit/test_admin_typing.py::test_missing_type_annotations",
    "error_type": "TypeError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_admin_typing.py\", line 22, in test_missing_type_annotations\n    check_types(mortgage_underwriting.modules.admin.services)\n  File \"type_checker.py\", line 10, in check_types\n    raise TypeError(f\"Function {func.__name__} missing annotations\")\nTypeError: Function get_user_by_id missing annotations",
    "error_message": "Function get_user_by_id missing annotations",
    "affected_code": [
      "mortgage_underwriting/modules/admin/services.py",
      "line 25"
    ],
    "suggested_fix": "Add complete type hints including return types to all public functions across services.py and routes.py.",
    "severity": "high"
  }
]
```