# Code Validation Report: Orchestrator Service

## Overall Status
Valid: False
Files Checked: 5
Files with Errors: 0
Total Warnings: 92

## Type Coverage


## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/exceptions.py:42:10: W292 no newline at end of file

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/models.py:4:101: E501 line too long (108 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/models.py:38:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/models.py:40:101: E501 line too long (129 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/models.py:42:101: E501 line too long (163 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/models.py:46:101: E501 line too long (116 > 100 characters)

### schemas.py
**Warnings:**
- Type hints missing in schemas.py::validate_sin: missing parameters, return type
- Type hints missing in schemas.py::validate_financials: missing return type
- schemas.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/schemas.py:39:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/schemas.py:60:1: W293 blank line contains whitespace

### services.py
**Warnings:**
- services.py: Type hint coverage only 88.88888888888889% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/services.py:12:101: E501 line too long (114 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/services.py:33:101: E501 line too long (103 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/services.py:36:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/services.py:42:1: W293 blank line contains whitespace

### routes.py

