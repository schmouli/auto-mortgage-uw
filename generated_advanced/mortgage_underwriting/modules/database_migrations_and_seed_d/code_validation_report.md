# Code Validation Report: Database Migrations & Seed Data

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 42

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 60.0%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/exceptions.py:5:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/exceptions.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/exceptions.py:11:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:8:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:16:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:18:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:22:101: E501 line too long (112 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:23:101: E501 line too long (103 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:5:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:7:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:13:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:17:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:23:1: E302 expected 2 blank lines, found 1

### services.py
**Warnings:**
- services.py: Type hint coverage only 60.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:28:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:34:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:38:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:5:1: F401 'mortgage_underwriting.modules.migration.schemas.MigrationStatusResponse' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:5:1: F401 'mortgage_underwriting.modules.migration.schemas.SeedHistoryResponse' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:15:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:23:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:29:1: E302 expected 2 blank lines, found 1

