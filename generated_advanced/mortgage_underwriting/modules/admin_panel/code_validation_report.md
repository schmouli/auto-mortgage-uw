# Code Validation Report: Admin Panel

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 12

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/exceptions.py:18:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/models.py:116:6: W292 no newline at end of file

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/schemas.py:9:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/schemas.py:225:15: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 76.92307692307693% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/services.py:2:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/services.py:2:1: F401 'typing.List' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/services.py:3:1: F401 'json' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/services.py:6:1: F401 'sqlalchemy.orm.selectinload' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/routes.py:2:1: F401 'typing.Any' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/admin_panel/routes.py:167:60: W292 no newline at end of file

### schema_model_consistency
**Errors:**
- Product: >50% of fields missing in ProductResponse - check schema/model field name synchronization

