# Code Validation Report: Database Migrations & Seed Data

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 43

## Type Coverage

- exceptions.py: 100%
- models.py: 0.0%
- schemas.py: 100%
- services.py: 66.7%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/exceptions.py:5:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/exceptions.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/exceptions.py:11:9: W292 no newline at end of file

### models.py
**Warnings:**
- models.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:3:1: F401 'sqlalchemy.Column' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:3:1: F401 'sqlalchemy.Numeric' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:3:1: F401 'sqlalchemy.Text' imported but unused

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:3:1: F401 'typing.Any' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:6:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:11:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:15:101: E501 line too long (101 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:18:1: E302 expected 2 blank lines, found 1

### services.py
**Warnings:**
- services.py: Type hint coverage only 66.66666666666666% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:4:1: F401 'sqlalchemy.select' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:10:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:30:101: E501 line too long (133 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:38:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:7:29: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:8:26: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:20:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:30:51: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:33:1: W293 blank line contains whitespace

