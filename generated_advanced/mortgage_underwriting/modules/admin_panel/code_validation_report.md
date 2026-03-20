# Code Validation Report: Admin Panel

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 69

## Type Coverage

- exceptions.py: 0.0%
- models.py: 100%
- schemas.py: 100%
- services.py: 90.9%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/exceptions.py:35:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/exceptions.py:36:45: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/models.py:4:1: F401 'sqlalchemy.Numeric' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/models.py:4:1: F401 'sqlalchemy.CheckConstraint' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/models.py:35:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/models.py:38:27: F821 undefined name 'User'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/models.py:52:101: E501 line too long (116 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/schemas.py:25:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/schemas.py:47:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/schemas.py:100:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/schemas.py:118:29: W292 no newline at end of file

### services.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/services.py:4:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/services.py:7:1: F401 'sqlalchemy.func as sql_func' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/services.py:29:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/services.py:33:57: W504 line break after binary operator
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/services.py:38:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/routes.py:1:1: F401 'datetime.datetime' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/routes.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/routes.py:40:17: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/routes.py:75:101: E501 line too long (118 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/routes.py:122:47: W292 no newline at end of file

