```json
[
  {
    "title": "Missing 'updated_at' field in migration script causes IntegrityError during seed",
    "description": "Seeding database fails due to missing 'updated_at' column in the borrowers table. The model defines updated_at, but migration does not include it.",
    "test_name": "tests/integration/test_seed_data_integration.py::test_seed_borrowers_table",
    "error_type": "IntegrityError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/usr/local/lib/python3.12/site-packages/sqlalchemy/engine/base.py\", line 1900, in _execute_context\n    self.dialect.do_execute(\n  File \"/usr/local/lib/python3.12/site-packages/sqlalchemy/engine/default.py\", line 717, in do_execute\n    cursor.execute(statement, parameters)\npsycopg2.errors.NotNullViolation: null value in column \"updated_at\" violates not-null constraint\nDETAIL:  Failing row contains (1, John, Doe, 1985-06-15, 123456789, 75000.0000, null).\n",
    "error_message": "null value in column \"updated_at\" violates not-null constraint",
    "affected_code": [
      "mortgage_underwriting/modules/borrower/models.py",
      "mortgage_underwriting/alembic/versions/2026_02_20_1234_add_borrower_table.py"
    ],
    "suggested_fix": "Update Alembic migration script to add updated_at column with default and onupdate settings matching model definition.",
    "severity": "high"
  },
  {
    "title": "Decimal precision mismatch between service and seeded data leads to AssertionError",
    "description": "The borrower income is stored as Decimal('75000') in seed, but calculated value uses float causing precision mismatch in assertions.",
    "test_name": "tests/unit/test_borrower_service.py::test_get_borrower_with_income_precision",
    "error_type": "AssertionError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/unit/test_borrower_service.py\", line 42, in test_get_borrower_with_income_precision\n    assert result.income == expected_income\nAssertionError: assert Decimal('75000.0000') == Decimal('75000')",
    "error_message": "assert Decimal('75000.0000') == Decimal('75000')",
    "affected_code": [
      "mortgage_underwriting/modules/borrower/services.py",
      "mortgage_underwriting/tests/fixtures/borrower_seeds.py"
    ],
    "suggested_fix": "Ensure all seed values use exact Decimal formatting with four decimal places to match financial standards.",
    "severity": "high"
  },
  {
    "title": "SIN field exposed in logs during borrower creation",
    "description": "During borrower creation via seed process, unhashed SIN was logged by mistake violating PIPEDA compliance.",
    "test_name": "tests/integration/test_logging_compliance.py::test_no_sin_in_logs_during_seed",
    "error_type": "ValueError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_logging_compliance.py\", line 31, in test_no_sin_in_logs_during_seed\n    raise ValueError(\"SIN detected in log output\")\nValueError: SIN detected in log output",
    "error_message": "SIN detected in log output",
    "affected_code": [
      "mortgage_underwriting/modules/borrower/models.py",
      "mortgage_underwriting/common/security.py"
    ],
    "suggested_fix": "Remove debug logging that includes raw SIN; ensure encryption occurs before any logging.",
    "severity": "critical"
  },
  {
    "title": "Alembic downgrade fails due to missing foreign key constraints in drop order",
    "description": "Downgrading alembic revision fails because loans table depends on borrowers which gets dropped first.",
    "test_name": "tests/integration/test_migrations_downgrade.py::test_downgrade_from_loans_to_initial",
    "error_type": "InternalError",
    "stack_trace": "Traceback (most recent call last):\n  File \"/app/tests/integration/test_migrations_downgrade.py\", line 28, in test_downgrade_from_loans_to_initial\n    command.downgrade(config, '-1')\n  File \"/usr/local/lib/python3.12/site-packages/alembic/command.py\", line 369, in downgrade\n    script.run_env()\npsycopg2.errors.DependentObjectsStillExist: cannot drop table borrowers because other objects depend on it",
    "error_message": "cannot drop table borrowers because other objects depend on it",
    "affected_code": [
      "mortgage_underwriting/alembic/versions/2026_02_21_5678_add_loans_table.py"
    ],
    "suggested_fix": "Adjust migration downgrade order to drop dependent tables before parent tables.",
    "severity": "high"
  }
]
```