# Code Validation Report: Authentication & User Management

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 53

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/exceptions.py:42:10: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/models.py:7:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/models.py:18:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/models.py:19:101: E501 line too long (137 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/models.py:22:101: E501 line too long (132 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/models.py:37:101: E501 line too long (116 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/schemas.py:8:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/schemas.py:17:84: W605 invalid escape sequence '\d'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/schemas.py:17:101: E501 line too long (122 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/schemas.py:17:109: W605 invalid escape sequence '\d'
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/schemas.py:46:45: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 57.14285714285714% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/services.py:12:1: F401 'mortgage_underwriting.common.exceptions.AppException' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/services.py:40:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/services.py:44:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/services.py:46:101: E501 line too long (103 > 100 characters)

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/routes.py:43:101: E501 line too long (128 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/routes.py:65:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/routes.py:67:101: E501 line too long (104 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/routes.py:68:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/routes.py:94:9: W292 no newline at end of file

### schema_model_consistency
**Errors:**
- User: >50% of fields missing in UserResponse - check schema/model field name synchronization

