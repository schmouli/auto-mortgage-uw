# Code Validation Report: Infrastructure & Deployment

## Overall Status
Valid: True
Files Checked: 5
Files with Errors: 0
Total Warnings: 34

## Type Coverage

- exceptions.py: 100%
- models.py: 100%
- schemas.py: 100%
- services.py: 75.0%
- routes.py: 100.0%

## Detailed Results

### exceptions.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/exceptions.py:24:22: W292 no newline at end of file
- exceptions.py: Found potential hardcoded values - consider moving to config/constants

### models.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/models.py:15:101: E501 line too long (119 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/models.py:21:101: E501 line too long (121 > 100 characters)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/models.py:41:6: W292 no newline at end of file

### schemas.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/schemas.py:27:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/schemas.py:47:1: E302 expected 2 blank lines, found 1
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/schemas.py:49:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/schemas.py:50:52: W292 no newline at end of file

### services.py
**Warnings:**
- services.py: Type hint coverage only 75.0% (target: 90%+)
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/services.py:17:1: F401 'mortgage_underwriting.modules.infra.exceptions.HealthCheckFailedError' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/services.py:35:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/services.py:38:1: W293 blank line contains whitespace
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/services.py:50:1: W293 blank line contains whitespace

### routes.py
**Warnings:**
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/routes.py:1:1: F401 'typing.Dict' imported but unused
- flake8: /workspace/generated_advanced/mortgage_underwriting/modules/infrastructure_and_deployment/routes.py:89:39: W292 no newline at end of file

