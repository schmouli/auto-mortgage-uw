# Code Validation Report: Orchestrator Service

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 77

## Type Coverage

- exceptions.py: 0.0%
- models.py: 0.0%
- schemas.py: 100.0%
- services.py: 90.0%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- exceptions.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/exceptions.py:24:62: W292 no newline at end of file

### models.py
**Warnings:**
- models.py: Type hint coverage only 0.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/models.py:7:1: F401 'sqlalchemy.UniqueConstraint' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/models.py:46:101: E501 line too long (118 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/models.py:51:101: E501 line too long (116 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/models.py:52:101: E501 line too long (137 > 100 characters)

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/schemas.py:12:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/schemas.py:129:52: W292 no newline at end of file

### services.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/services.py:4:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/services.py:14:101: E501 line too long (127 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/services.py:28:14: W291 trailing whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/services.py:63:101: E501 line too long (107 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/services.py:97:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/routes.py:2:1: F401 'typing.Optional' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/routes.py:16:1: F401 'mortgage_underwriting.modules.orchestrator.models.Application' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/routes.py:32:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/routes.py:40:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/orchestrator_service/routes.py:46:1: W293 blank line contains whitespace

