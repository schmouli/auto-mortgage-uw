```json
[
  {
    "title": "Client Portal List Endpoint Lacks Pagination",
    "description": "Unit test failure indicates that listing clients does not support pagination parameters such as 'skip' and 'limit'. This leads to potential performance degradation and violates regulatory expectations around data access control.",
    "test_name": "tests/unit/test_client_portal.py::test_list_clients_no_pagination",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_client_portal.py\", line 67, in test_list_clients_no_pagination\n    assert response.json()['clients'][0]['id'] == client1.id\nIndexError: list index out of range",
    "error_message": "list index out of range",
    "affected_code": [
      "mortgage_underwriting/modules/client_portal/routes.py",
      "line 32"
    ],
    "suggested_fix": "Implement query parameters skip and limit with maximum cap at 100 in route handler for listing clients. Apply them in service layer during database fetch.",
    "severity": "high"
  },
  {
    "title": "SQL Injection Risk in Client Search Query",
    "description": "The client search functionality uses string formatting instead of parameterized queries, exposing a critical SQL injection vulnerability.",
    "test_name": "tests/unit/test_client_portal.py::test_search_clients_sanitized_input",
    "error_type": "SyntaxError",
    "stack_trace": "Traceback (most recent call last):\n  File \"mortgage_underwriting/modules/client_portal/services.py\", line 54, in search_clients\n    result = await session.execute(text(f\"SELECT * FROM clients WHERE name LIKE '%{query}%'\"))\n  ...\nsqlalchemy.exc.StatementError: (sqlalchemy.exc.ProgrammingError) syntax error near \"{query}\"",
    "error_message": "(sqlalchemy.exc.ProgrammingError) syntax error near \"{query}\"",
    "affected_code": [
      "mortgage_underwriting/modules/client_portal/services.py",
      "line 54"
    ],
    "suggested_fix": "Replace raw string interpolation with SQLAlchemy's built-in parameter binding using :param syntax in text() or switch to ORM-based querying.",
    "severity": "high"
  },
  {
    "title": "Missing Foreign Key Cascade Behavior",
    "description": "Foreign key relationships in client-related models do not define ON DELETE behaviors, which may lead to orphaned records and referential integrity issues.",
    "test_name": "tests/integration/test_client_cascade.py::test_delete_client_cascades_related_records",
    "error_type": "IntegrityError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/integration/test_client_cascade.py\", line 45, in test_delete_client_cascades_related_records\n    await client_service.delete(client_id)\n  File \"mortgage_underwriting/modules/client_portal/services.py\", line 112, in delete\n    await session.commit()\nsqlalchemy.exc.IntegrityError: FOREIGN KEY constraint failed",
    "error_message": "FOREIGN KEY constraint failed",
    "affected_code": [
      "mortgage_underwriting/modules/client_portal/models.py",
      "line 28"
    ],
    "suggested_fix": "Update all ForeignKey definitions to include explicit `ondelete=` clauses like CASCADE or SET NULL based on business rules.",
    "severity": "high"
  },
  {
    "title": "Type Hinting Missing in Public Functions",
    "description": "Several public-facing functions lack proper type annotations, reducing maintainability and increasing risk of runtime errors due to incorrect usage.",
    "test_name": "N/A – Static Analysis Failure",
    "error_type": "mypy error",
    "stack_trace": "/mortgage_underwriting/modules/client_portal/services.py:78: error: Function is missing a type annotation\n/mortgage_underwriting/modules/client_portal/routes.py:44: error: Call to untyped function in typed context",
    "error_message": "Function is missing a type annotation",
    "affected_code": [
      "mortgage_underwriting/modules/client_portal/services.py",
      "multiple lines"
    ],
    "suggested_fix": "Annotate all function signatures including arguments and return types using typing module constructs.",
    "severity": "high"
  },
  {
    "title": "Float Used Instead of Decimal for Financial Fields",
    "description": "Client income fields stored and processed as floats instead of Decimals causing precision loss, violating OSFI B-20 compliance standards.",
    "test_name": "tests/unit/test_client_validation.py::test_monetary_precision_check",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"tests/unit/test_client_validation.py\", line 22, in test_monetary_precision_check\n    assert isinstance(client.monthly_income, Decimal)\nAssertionError",
    "error_message": "assert isinstance(client.monthly_income, Decimal)",
    "affected_code": [
      "mortgage_underwriting/modules/client_portal/models.py",
      "line 19"
    ],
    "suggested_fix": "Change column definition from Float to Numeric(19,4) and ensure all references use Decimal throughout services and schemas.",
    "severity": "high"
  }
]
```