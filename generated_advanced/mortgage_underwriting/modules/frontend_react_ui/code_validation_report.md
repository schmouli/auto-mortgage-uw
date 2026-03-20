# Code Validation Report: Frontend React UI

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 30

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/exceptions.py:13:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/models.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/models.py:3:1: F401 'sqlalchemy.Numeric' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/models.py:19:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/models.py:22:101: E501 line too long (101 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/models.py:29:101: E501 line too long (137 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/schemas.py:36:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/schemas.py:61:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/schemas.py:65:25: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 88.88888888888889% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/services.py:39:101: E501 line too long (133 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/services.py:45:101: E501 line too long (119 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/services.py:49:101: E501 line too long (113 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/services.py:82:101: E501 line too long (109 > 100 characters)

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/routes.py:19:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/routes.py:29:101: E501 line too long (130 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/routes.py:41:101: E501 line too long (139 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/routes.py:66:101: E501 line too long (139 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/frontend_react_ui/routes.py:79:101: E501 line too long (139 > 100 characters)

### schema_model_consistency
**Errors:**
- UIComponent: >50% of fields missing in UIComponentResponse - check schema/model field name synchronization

