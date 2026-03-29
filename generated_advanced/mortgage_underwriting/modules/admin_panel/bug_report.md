```json
[
  {
    "title": "Hardcoded configuration values in admin panel services",
    "description": "Configuration values such as pagination limits and default statuses are hardcoded directly in service logic instead of being sourced from config or constants.",
    "test_name": "tests/unit/test_admin_panel_services.py::test_list_users_pagination_limit_exceeded",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_admin_panel_services.py\", line 78, in test_list_users_pagination_limit_exceeded\n    assert result.limit == 100\nAssertionError: assert 200 == 100",
    "error_message": "assert 200 == 100",
    "affected_code": [
      "mortgage_underwriting/modules/admin_panel/services.py",
      "line 32"
    ],
    "suggested_fix": "Move hardcoded limit values into a centralized config object or constant file, e.g., MAX_PAGINATION_LIMIT = 100 in common/config.py",
    "severity": "high"
  },
  {
    "title": "Missing index on frequently queried email column",
    "description": "Query performance degradation observed during user listing operations due to lack of index on the 'email' field used for filtering.",
    "test_name": "tests/integration/test_admin_panel_integration.py::test_filter_users_by_email_performance",
    "error_type": "TimeoutError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/integration/test_admin_panel_integration.py\", line 112, in test_filter_users_by_email_performance\n    response = client.get('/api/v1/admin/users?email=test@example.com')\n  ...\ntimeout_decorator.timeout_decorator.TimeoutError: Function execution timed out after 5 seconds",
    "error_message": "Function execution timed out after 5 seconds",
    "affected_code": [
      "mortgage_underwriting/modules/admin_panel/models.py",
      "line 18"
    ],
    "suggested_fix": "Add database index to the User.email column using Index('ix_user_email', User.email)",
    "severity": "high"
  },
  {
    "title": "SQL Injection vulnerability via raw query construction",
    "description": "Raw string formatting is used to construct SQL queries in admin panel services, exposing potential SQL injection risks.",
    "test_name": "tests/unit/test_admin_panel_security.py::test_sql_injection_in_user_search",
    "error_type": "SecurityViolation",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_admin_panel_security.py\", line 45, in test_sql_injection_in_user_search\n    result = search_users(\"'; DROP TABLE users; --\")\n  File \"mortgage_underwriting/modules/admin_panel/services.py\", line 98, in search_users\n    session.execute(text(f\"SELECT * FROM users WHERE name LIKE '%{term}%'\"))\nsqlalchemy.exc.ProgrammingError: (psycopg2.ProgrammingError) syntax error at or near \"DROP\"",
    "error_message": "(psycopg2.ProgrammingError) syntax error at or near \"DROP\"",
    "affected_code": [
      "mortgage_underwriting/modules/admin_panel/services.py",
      "line 98"
    ],
    "suggested_fix": "Replace raw string interpolation with SQLAlchemy's built-in parameter binding: session.execute(select(User).where(User.name.like(f'%{term}%')))",
    "severity": "high"
  },
  {
    "title": "Foreign key constraint missing ondelete behavior",
    "description": "Foreign key relationships do not define an ON DELETE action, which may lead to orphaned records or unexpected integrity errors.",
    "test_name": "tests/unit/test_admin_panel_models.py::test_user_role_cascade_delete",
    "error_type": "IntegrityError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/workspace/mortgage_underwriting/tests/unit/test_admin_panel_models.py\", line 63, in test_user_role_cascade_delete\n    session.delete(role)\n    session.commit()\n  File \"/usr/local/lib/python3.12/site-packages/sqlalchemy/orm/session.py\", line 1431, in commit\n    self._transaction.commit()\nsqlalchemy.exc.IntegrityError: (psycopg2.errors.ForeignKeyViolation) update or delete on table \"roles\" violates foreign key constraint \"fk_users_role_id\" on table \"users\"",
    "error_message": "(psycopg2.errors.ForeignKeyViolation) update or delete on table \"roles\" violates foreign key constraint \"fk_users_role_id\" on table \"users\"",
    "affected_code": [
      "mortgage_underwriting/modules/admin_panel/models.py",
      "line 25"
    ],
    "suggested_fix": "Define ForeignKey with explicit ondelete behavior: role_id = Column(Integer, ForeignKey('roles.id', ondelete='SET NULL'))",
    "severity": "high"
  }
]
```