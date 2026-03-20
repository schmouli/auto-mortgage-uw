# Code Validation Report: Decision Service

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 75

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 75.0%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/exceptions.py:13:9: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:14:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:19:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:22:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:24:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/models.py:30:1: W293 blank line contains whitespace

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:26:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:29:101: E501 line too long (110 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:33:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:38:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/schemas.py:45:1: W293 blank line contains whitespace

### services.py
**Warnings:**
- services.py: Type hint coverage only 75.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:34:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:39:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:41:101: E501 line too long (102 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/services.py:42:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:7:1: F401 'mortgage_underwriting.modules.decision.schemas.DecisionListResponse' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:19:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:22:1: E304 blank lines found after function decorator
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:27:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/decision_service/routes.py:40:1: E302 expected 2 blank lines, found 1

