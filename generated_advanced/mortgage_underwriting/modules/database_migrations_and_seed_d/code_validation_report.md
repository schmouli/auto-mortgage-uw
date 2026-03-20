# Code Validation Report: Database Migrations & Seed Data

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 47

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 71.4%
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
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:23:101: E501 line too long (106 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:27:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:27:122: W292 no newline at end of file

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:5:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:10:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:11:101: E501 line too long (119 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:13:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:17:1: E302 expected 2 blank lines, found 1

### services.py
**Warnings:**
- services.py: Type hint coverage only 71.42857142857143% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:5:101: E501 line too long (118 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:59:101: E501 line too long (110 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:60:101: E501 line too long (112 > 100 characters)

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:2:1: F401 'fastapi.HTTPException' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:13:101: E501 line too long (101 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:17:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:21:6: F821 undefined name 'Dict'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:21:16: F821 undefined name 'Any'

