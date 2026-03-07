# Code Validation Report: Client Portal

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 52

## Type Coverage

- exceptions.py: 0.0%
- models.py: 100%
- schemas.py: 100%
- services.py: 66.7%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/exceptions.py:17:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/exceptions.py:18:63: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:3:1: F401 'sqlalchemy.Numeric' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:11:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:19:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:21:101: E501 line too long (101 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/schemas.py:8:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/schemas.py:125:25: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 66.66666666666666% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/services.py:2:1: F401 'typing.List' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/services.py:2:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/services.py:2:1: F401 'typing.Tuple' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/services.py:5:1: F401 'sqlalchemy.orm.selectinload' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/routes.py:3:1: F401 'fastapi.HTTPException' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/routes.py:25:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/routes.py:34:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/routes.py:43:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/routes.py:52:1: E302 expected 2 blank lines, found 1

