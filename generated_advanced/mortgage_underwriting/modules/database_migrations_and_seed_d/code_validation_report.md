# Code Validation Report: Database Migrations & Seed Data

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 13

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 75.0%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/exceptions.py:13:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:11:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:18:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:20:1: E305 expected 2 blank lines after class or function definition, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/models.py:20:41: W292 no newline at end of file

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:22:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/schemas.py:27:25: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 75.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:10:101: E501 line too long (105 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:32:101: E501 line too long (119 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:39:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/services.py:50:44: W292 no newline at end of file

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/database_migrations_and_seed_d/routes.py:57:46: W292 no newline at end of file

