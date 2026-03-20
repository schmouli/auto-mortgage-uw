# Code Validation Report: Client Portal

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 83

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/exceptions.py:11:101: E501 line too long (101 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/exceptions.py:18:63: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:21:101: E501 line too long (124 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:24:101: E501 line too long (106 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:25:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:28:18: F821 undefined name 'User'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/models.py:44:101: E501 line too long (121 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/schemas.py:22:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/schemas.py:49:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/schemas.py:66:101: E501 line too long (101 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/schemas.py:90:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/schemas.py:102:1: W293 blank line contains whitespace

### services.py
**Warnings:**
- services.py: Type hint coverage only 88.88888888888889% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/services.py:2:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/services.py:8:101: E501 line too long (106 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/services.py:9:1: F401 'mortgage_underwriting.modules.portal.schemas.NotificationCreate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/services.py:9:1: F401 'mortgage_underwriting.modules.portal.schemas.NotificationUpdate' imported but unused

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/routes.py:1:1: F401 'datetime.datetime' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/routes.py:2:1: F401 'typing.List' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/routes.py:8:1: F401 'mortgage_underwriting.modules.portal.schemas.NotificationUpdate' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/routes.py:29:101: E501 line too long (110 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/client_portal/routes.py:158:10: W292 no newline at end of file

### schema_model_consistency
**Errors:**
- ClientPortalActivity: >50% of fields missing in ClientPortalActivityResponse - check schema/model field name synchronization
- UserPreference: >50% of fields missing in UserPreferenceResponse - check schema/model field name synchronization

