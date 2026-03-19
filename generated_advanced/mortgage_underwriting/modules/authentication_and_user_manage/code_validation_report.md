# Code Validation Report: Authentication & User Management

## Overall Status
Valid: False
Files Checked: 6
Files with Errors: 1
Total Warnings: 50

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/exceptions.py:30:73: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/models.py:8:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/models.py:14:101: E501 line too long (103 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/models.py:18:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/models.py:19:101: E501 line too long (137 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/models.py:22:101: E501 line too long (132 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/schemas.py:14:101: E501 line too long (129 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/schemas.py:44:71: W292 no newline at end of file
- schemas.py: Found potential hardcoded values - consider moving to config/constants

### services.py
**Warnings:**
- services.py: Type hint coverage only 62.5% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/services.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/services.py:27:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/services.py:30:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/services.py:39:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/routes.py:1:1: F401 'datetime.datetime' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/routes.py:2:1: F401 'decimal.Decimal' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/routes.py:7:1: F401 'fastapi.Security' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/routes.py:32:101: E501 line too long (126 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/authentication_and_user_manage/routes.py:33:101: E501 line too long (136 > 100 characters)

### schema_model_consistency
**Errors:**
- RefreshToken: >50% of fields missing in RefreshTokenRequest - check schema/model field name synchronization

