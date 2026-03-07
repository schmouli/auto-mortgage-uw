# Code Validation Report: Frontend React UI

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 69

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/exceptions.py:3:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/exceptions.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/exceptions.py:11:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/exceptions.py:13:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/models.py:4:1: F401 'sqlalchemy.dialects.postgresql.UUID as PG_UUID' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/models.py:8:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/models.py:10:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/models.py:13:101: E501 line too long (113 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/models.py:16:101: E501 line too long (116 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/schemas.py:5:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/schemas.py:11:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/schemas.py:14:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/schemas.py:20:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/schemas.py:22:1: W293 blank line contains whitespace

### services.py
**Warnings:**
- services.py: Type hint coverage only 83.33333333333334% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/services.py:1:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/services.py:3:1: F401 'sqlalchemy.update' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/services.py:3:1: F401 'sqlalchemy.delete' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/services.py:8:1: F401 '.schemas' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/routes.py:12:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/routes.py:12:101: E501 line too long (108 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/routes.py:24:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/routes.py:36:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/routes.py:49:1: E302 expected 2 blank lines, found 1

### schema_model_consistency
**Errors:**
- UiComponent: >50% of fields missing in UiComponentResponse - check schema/model field name synchronization
- PageComponent: >50% of fields missing in PageComponentResponse - check schema/model field name synchronization

