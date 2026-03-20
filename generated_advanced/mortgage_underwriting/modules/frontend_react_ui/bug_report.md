```json
[
  {
    "title": "Hardcoded interest rate values in frontend calculator",
    "description": "Frontend UI uses hardcoded interest rates instead of fetching from backend configuration. This violates the dynamic rate loading requirement and causes incorrect calculations during stress testing.",
    "test_name": "tests/unit/test_frontend_calculator.py::test_interest_rate_dynamic_loading",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_frontend_calculator.py\", line 32, in test_interest_rate_dynamic_loading\n    assert calculator.get_rate() == config.DEFAULT_RATE\nAssertionError: 0.0525 != 0.0675",
    "error_message": "Expected rate to match backend config value, got hardcoded fallback",
    "affected_code": ["frontend/src/components/MortgageCalculator.jsx", "line 18"],
    "suggested_fix": "Replace hardcoded rate constants with async fetch from /api/v1/rates/current endpoint",
    "severity": "high"
  },
  {
    "title": "Missing index on email column causes slow user lookup",
    "description": "User search by email takes over 2 seconds due to missing database index. Impacts login performance and admin panel usability.",
    "test_name": "tests/integration/test_user_search_performance.py::test_email_search_speed",
    "error_type": "TimeoutError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/integration/test_user_search_performance.py\", line 25, in test_email_search_speed\n    response = client.get(f\"/api/v1/users?email={test_email}\")\n  File \"httpx/_client.py\", line 1234, in get\n    return self.request(...)\n  File \"httpx/_client.py\", line 987, in request\n    raise TimeoutException()",
    "error_message": "Request timed out after 2000ms waiting for user search response",
    "affected_code": ["mortgage_underwriting/modules/user/models.py", "line 22"],
    "suggested_fix": "Add Index('ix_users_email', User.email) to User model and generate migration",
    "severity": "high"
  },
  {
    "title": "Pagination not implemented on mortgage applications list",
    "description": "GET /api/v1/applications returns all records without pagination support. With 50k+ records this causes memory exhaustion and timeouts.",
    "test_name": "tests/integration/test_applications_pagination.py::test_list_applications_no_limit",
    "error_type": "MemoryError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/integration/test_applications_pagination.py\", line 18, in test_list_applications_no_limit\n    resp = client.get(\"/api/v1/applications\")\n  File \"httpx/_client.py\", line 1234, in get\n    return self.request(...)\n  File \"httpx/_client.py\", line 987, in request\n    raise MemoryError('Response too large')",
    "error_message": "Response payload exceeded maximum allowed size (50MB)",
    "affected_code": ["mortgage_underwriting/modules/application/routes.py", "line 35"],
    "suggested_fix": "Implement skip/limit query params with max limit=100 validation",
    "severity": "high"
  },
  {
    "title": "SQL injection vulnerability in borrower search filter",
    "description": "Borrower search accepts raw SQL fragments in query parameters leading to potential SQL injection attacks.",
    "test_name": "tests/unit/test_borrower_security.py::test_sql_injection_prevention",
    "error_type": "SecurityViolation",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_borrower_security.py\", line 41, in test_sql_injection_prevention\n    result = borrower_service.search(\"'; DROP TABLE borrowers; --\")\n  File \"mortgage_underwriting/modules/borrower/services.py\", line 67, in search\n    session.execute(text(query))\nsqlalchemy.exc.ProgrammingError: (psycopg2.errors.SyntaxError) unterminated quoted string",
    "error_message": "Raw SQL execution detected without parameter binding",
    "affected_code": ["mortgage_underwriting/modules/borrower/services.py", "line 65"],
    "suggested_fix": "Use SQLAlchemy query builder with bound parameters instead of raw SQL strings",
    "severity": "high"
  },
  {
    "title": "Foreign key constraint missing cascade delete behavior",
    "description": "Deleting a user does not automatically remove associated mortgage applications causing orphaned data and referential integrity issues.",
    "test_name": "tests/integration/test_user_deletion_cascade.py::test_user_delete_cascades_applications",
    "error_type": "IntegrityError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/integration/test_user_deletion_cascade.py\", line 28, in test_user_delete_cascades_applications\n    client.delete(f\"/api/v1/users/{user_id}\")\n  File \"httpx/_client.py\", line 1234, in delete\n    return self.request(...)\n  File \"httpx/_client.py\", line 987, in request\n    raise IntegrityError('foreign key constraint violated')",
    "error_message": "Cannot delete user because applications exist referencing user_id",
    "affected_code": ["mortgage_underwriting/modules/application/models.py", "line 33"],
    "suggested_fix": "Update Application.user_id ForeignKey definition to include ondelete='CASCADE'",
    "severity": "high"
  }
]
```