# Code Validation Report: Decision Service

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 55

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 75.0%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/exceptions.py:18:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:16:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:29:101: E501 line too long (115 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:31:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:36:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:40:1: W293 blank line contains whitespace

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:10:101: E501 line too long (122 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:11:101: E501 line too long (107 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:13:101: E501 line too long (109 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:55:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:69:1: W293 blank line contains whitespace

### services.py
**Warnings:**
- services.py: Type hint coverage only 75.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:28:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:32:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:35:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:40:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:22:26: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:23:11: E128 continuation line under-indented for visual indent
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:23:51: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:24:11: E128 continuation line under-indented for visual indent
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:25:11: E128 continuation line under-indented for visual indent

